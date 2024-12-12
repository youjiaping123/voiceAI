import paho.mqtt.client as mqtt
import json
import azure.cognitiveservices.speech as speechsdk
import pyttsx3
import io
from openai import OpenAI
from dotenv import load_dotenv
import os
import wave
import time

# 加载环境变量
load_dotenv()

class VoiceAIChatbot:
    def __init__(self):
        # 配置Azure Speech服务
        self.speech_config = speechsdk.SpeechConfig(
            subscription=os.getenv('SPEECH_KEY'), 
            region=os.getenv('SPEECH_REGION')
        )
        self.speech_config.speech_recognition_language = "zh-CN"
        
        # 配置语音合成
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 200)    # 设置语速
        self.engine.setProperty('volume', 1.0)  # 设置音量
        
        # 配置 OpenAI
        self.ai_client = OpenAI(
            api_key=os.getenv("API_KEY"),
            base_url=os.getenv("BASE_URL")
        )
        
        # MQTT客户端设置
        self.mqtt_client = mqtt.Client(protocol=mqtt.MQTTv311)
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        
        # 添加用于流式处理的变量
        self.audio_stream = None
        self.push_stream = None
        self.speech_recognizer = None
        self.is_recognizing = False
        
    def on_connect(self, client, userdata, flags, rc):
        print("语音AI聊天机器人已连接")
        client.subscribe("voice/stream")  # 订阅音频流数据主题
        
    def start_stream_recognition(self):
        """初始化流式语音识别"""
        try:
            # 创建推送流
            self.push_stream = speechsdk.audio.PushAudioInputStream()
            audio_config = speechsdk.audio.AudioConfig(stream=self.push_stream)
            
            # 创建语音识别器
            self.speech_recognizer = speechsdk.SpeechRecognizer(
                speech_config=self.speech_config, 
                audio_config=audio_config
            )
            
            # 设置识别回调
            def handle_result(evt):
                # 处理中间结果
                if evt.result.reason == speechsdk.ResultReason.RecognizingSpeech:
                    print(f"识别中: {evt.result.text}")
                # 处理最终结果
                elif evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    print(f"识别完成: {evt.result.text}")
                    if evt.result.text.strip():  # 确保不是空文本
                        # 获取AI回复并转换为语音
                        ai_response = self.get_ai_response(evt.result.text)
                        print(f"AI回复: {ai_response}")
                        self.text_to_speech(ai_response)
                # 处理错误
                elif evt.result.reason == speechsdk.ResultReason.NoMatch:
                    print(f"无法识别语音: {evt.result.no_match_details}")
            
            # 连接识别事件
            self.speech_recognizer.recognizing.connect(handle_result)  # 添加中间结果处理
            self.speech_recognizer.recognized.connect(handle_result)
            self.speech_recognizer.canceled.connect(lambda evt: print(f"识别取消: {evt.reason}"))
            
            # 开始连续识别
            self.speech_recognizer.start_continuous_recognition()
            self.is_recognizing = True
            print("开始流式语音识别...")
            
        except Exception as e:
            print(f"启动流式识别时出错: {str(e)}")
            self.stop_stream_recognition()
    
    def stop_stream_recognition(self):
        """停止流式语音识别"""
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
        if msg.topic == "voice/stream":
            try:
                if msg.payload == b"END_OF_STREAM":
                    print("收到结束标记，停止识别...")
                    self.stop_stream_recognition()
                    return
                
                # 果识别器未启动，则启动它
                if not self.is_recognizing:
                    self.start_stream_recognition()
                
                # 将音频数据写入推送流
                if self.push_stream:
                    self.push_stream.write(msg.payload)
                
            except Exception as e:
                print(f"处理音频流数据时出错: {str(e)}")
                self.stop_stream_recognition()

    def get_ai_response(self, message):
        try:
            # 使用流式响应
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
            
            print()  # 换行
            return full_response
            
        except Exception as e:
            print(f"调用 AI API 出错: {str(e)}")
            return "抱歉，我现在无法回答。"
            
    def text_to_speech(self, text):
        synthesizer = None
        try:
            print("正在生成语音回复...")
            
            # 配置语音合成
            speech_config = speechsdk.SpeechConfig(
                subscription=os.getenv('SPEECH_KEY'), 
                region=os.getenv('SPEECH_REGION')
            )
            
            # 配置语音参数
            speech_config.speech_synthesis_voice_name = "zh-CN-XiaoxiaoNeural"
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
            )
            
            # 使用内存流接收音频数据
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
                # 获取音频数据
                audio_data = audio_stream.getvalue()
                print(f"音频合成完成，数据大小: {len(audio_data)} 字节")
                
                # 发布音频数据到MQTT
                result = self.mqtt_client.publish("voice/response", audio_data)
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    print("语音回复已发送")
                else:
                    print(f"发送失败，错误码: {result.rc}")
            else:
                print(f"语音合成失败: {result.reason}")
                
        except Exception as e:
            print(f"语音合成错误: {str(e)}")
            import traceback
            print(traceback.format_exc())
        
        finally:
            # 释放资源
            if synthesizer:
                synthesizer = None
    
    def start(self):
        # 连接到MQTT服务器
        mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
        mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
        
        print(f"正在连接到MQTT服务器 {mqtt_broker}:{mqtt_port}")
        self.mqtt_client.connect(mqtt_broker, mqtt_port)
        self.mqtt_client.loop_forever()

if __name__ == "__main__":
    chatbot = VoiceAIChatbot()
    chatbot.start() 