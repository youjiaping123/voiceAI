import paho.mqtt.client as mqtt  # MQTT客户端库，用于消息通信
import json
import azure.cognitiveservices.speech as speechsdk  # Azure语音服务SDK
import pyttsx3  # 文字转语音引擎
import io
from openai import OpenAI  # OpenAI API客户端
from dotenv import load_dotenv  # 环境变量加载工具
import os
import wave
import time

# 加载.env文件中的环境变量
load_dotenv()

class VoiceAIChatbot:
    def __init__(self):
        # 初始化Azure语音服务配置
        self.speech_config = speechsdk.SpeechConfig(
            subscription=os.getenv('SPEECH_KEY'), 
            region=os.getenv('SPEECH_REGION')
        )
        self.speech_config.speech_recognition_language = "zh-CN"  # 设置语音识别语言为中文
        
        # 初始化OpenAI客户端
        self.ai_client = OpenAI(
            api_key=os.getenv("API_KEY"),
            base_url=os.getenv("BASE_URL")
        )
        
        # 初始化MQTT客户端
        self.mqtt_client = mqtt.Client(protocol=mqtt.MQTTv311)
        self.mqtt_client.on_connect = self.on_connect  # 设置连接回调
        self.mqtt_client.on_message = self.on_message  # 设置消息接收回调
        
        # 初始化流式处理相关变量
        self.audio_stream = None  # 音频流对象
        self.push_stream = None   # 推送流对象
        self.speech_recognizer = None  # 语音识别器
        self.is_recognizing = False    # 识别状态标志
    
    def on_connect(self, client, userdata, flags, rc):
        """MQTT连接成功回调函数"""
        print("语音AI聊天机器人已连接")
        client.subscribe("voice/stream")  # 订阅音频流数据主题
    
    def start_stream_recognition(self):
        """初始化并启动流式语音识别"""
        try:
            # 创建音频推送流
            self.push_stream = speechsdk.audio.PushAudioInputStream()
            audio_config = speechsdk.audio.AudioConfig(stream=self.push_stream)
            
            # 创建语音识别器
            self.speech_recognizer = speechsdk.SpeechRecognizer(
                speech_config=self.speech_config, 
                audio_config=audio_config
            )
            
            def handle_result(evt):
                """处理语音识别结果的回调函数"""
                # 处理识别中的临时结果
                if evt.result.reason == speechsdk.ResultReason.RecognizingSpeech:
                    print(f"识别中: {evt.result.text}")
                # 处理最终识别结果
                elif evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    print(f"识别完成: {evt.result.text}")
                    if evt.result.text.strip():  # 确保识别结果不为空
                        # 获取AI回复并转换为语音
                        ai_response = self.get_ai_response(evt.result.text)
                        self.text_to_speech(ai_response)
                # 处理识别错误
                elif evt.result.reason == speechsdk.ResultReason.NoMatch:
                    print(f"无法识别语音: {evt.result.no_match_details}")
            
            # 注册识别事件处理器
            self.speech_recognizer.recognizing.connect(handle_result)
            self.speech_recognizer.recognized.connect(handle_result)
            self.speech_recognizer.canceled.connect(lambda evt: print(f"识别取消: {evt.reason}"))
            
            # 启动连续识别
            self.speech_recognizer.start_continuous_recognition()
            self.is_recognizing = True
            print("开始流式语音识别...")
            
        except Exception as e:
            print(f"启动流式识别时出错: {str(e)}")
            self.stop_stream_recognition()
    
    def stop_stream_recognition(self):
        """停止流式语音识别并清理资源"""
        try:
            if self.speech_recognizer and self.is_recognizing:
                self.speech_recognizer.stop_continuous_recognition()
                self.is_recognizing = False
            if self.push_stream:
                self.push_stream.close()
            self.push_stream = None
            self.speech_recognizer = None
            print("流式语音识别已停止")
        except Exception as e:
            print(f"停止流式识别时出错: {str(e)}")
    
    def on_message(self, client, userdata, msg):
        """处理接收到的MQTT消息"""
        if msg.topic == "voice/stream":
            try:
                # 检查是否收到结束标记
                if msg.payload == b"END_OF_STREAM":
                    print("收到结束标记，停止识别...")
                    self.stop_stream_recognition()
                    return
                
                # 如果识别器未启动，则启动它
                if not self.is_recognizing:
                    self.start_stream_recognition()
                
                # 将接收到的音频数据写入推送流
                if self.push_stream:
                    self.push_stream.write(msg.payload)
                
            except Exception as e:
                print(f"处理音频流数据时出错: {str(e)}")
                self.stop_stream_recognition()

    def get_ai_response(self, message):
        """获取AI的回复"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 使用流式响应调用AI API
                response_stream = self.ai_client.chat.completions.create(
                    model="claude-3-5-haiku-20241022",
                    messages=[
                        {"role": "system", "content": "你是一个简洁友好的AI助手，回答要简短精确。"},
                        {"role": "user", "content": message}
                    ],
                    stream=True  # 启用流式响应
                )
                
                # 收集完整响应
                full_response = ""
                print("AI正在回复: ", end="", flush=True)
                
                for chunk in response_stream:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        print(content, end="", flush=True)
                
                print()
                return full_response
                
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                print(f"重试AI调用 ({attempt + 1}/{max_retries})")
                time.sleep(1)

    def text_to_speech(self, text):
        """将文本转换为语音并通过MQTT发送"""
        synthesizer = None
        try:
            print("正在生成语音回复...")
            speech_config = speechsdk.SpeechConfig(
                subscription=os.getenv('SPEECH_KEY'), 
                region=os.getenv('SPEECH_REGION')
            )
            
            # 设置语音合成参数
            speech_config.speech_synthesis_voice_name = "zh-CN-XiaoxiaoNeural"
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
            )
            
            # 创建内存流存储音频数据
            audio_stream = io.BytesIO()
            
            def audio_callback(evt):
                if evt.result.reason == speechsdk.ResultReason.SynthesizingAudio:
                    audio_stream.write(evt.result.audio_data)
            
            # 创建语音合成器
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)
            synthesizer.synthesizing.connect(audio_callback)
            
            # 执行语音合成
            result = synthesizer.speak_text_async(text).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                audio_data = audio_stream.getvalue()
                print(f"音频合成完成，数据大小: {len(audio_data)} 字节")
                
                # 发送音频数据
                result = self.mqtt_client.publish("voice/response", audio_data)
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    print("语音回复已发送")
                else:
                    print(f"发送失败，错误码: {result.rc}")
            else:
                print(f"语音合成失败: {result.reason}")
                
        except Exception as e:
            print(f"语音合成错误: {str(e)}")
        finally:
            if synthesizer:
                synthesizer.close()

    def start(self):
        """启动聊天机器人服务"""
        # 连接到MQTT服务器
        mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
        mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
        
        print(f"正在连接到MQTT服务器 {mqtt_broker}:{mqtt_port}")
        self.mqtt_client.connect(mqtt_broker, mqtt_port)
        self.mqtt_client.loop_forever()  # 开始MQTT事件循环

    def stop(self):
        """优雅地停止服务"""
        try:
            self.stop_stream_recognition()
            self.mqtt_client.disconnect()
            print("服务已停止")
        except Exception as e:
            print(f"停止服务时出错: {str(e)}")

if __name__ == "__main__":
    chatbot = VoiceAIChatbot()
    try:
        chatbot.start()
    except KeyboardInterrupt:
        print("\n正在停止服务...")
        chatbot.stop()
    except Exception as e:
        print(f"服务出错: {str(e)}")
        chatbot.stop() 