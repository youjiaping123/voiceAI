import paho.mqtt.client as mqtt
import azure.cognitiveservices.speech as speechsdk
import io
from openai import OpenAI
from dotenv import load_dotenv
import os
import wave
import time

load_dotenv()

class VoiceAIChatbot:
    def __init__(self):
        # 初始化Azure语音服务
        self.speech_config = speechsdk.SpeechConfig(
            subscription=os.getenv('SPEECH_KEY'), 
            region=os.getenv('SPEECH_REGION')
        )
        self.speech_config.speech_recognition_language = "zh-CN"
        
        # 初始化OpenAI客户端
        self.ai_client = OpenAI(
            api_key=os.getenv("API_KEY"),
            base_url=os.getenv("BASE_URL")
        )
        
        # 初始化MQTT客户端
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        
        self.push_stream = None
        self.speech_recognizer = None
        self.is_recognizing = False
    
    def on_connect(self, client, userdata, flags, rc):
        print("已连接到MQTT服务器")
        client.subscribe("voice/stream")
    
    def start_stream_recognition(self):
        try:
            print("正在启动语音识别...")
            self.push_stream = speechsdk.audio.PushAudioInputStream()
            audio_config = speechsdk.audio.AudioConfig(stream=self.push_stream)
            
            self.speech_recognizer = speechsdk.SpeechRecognizer(
                speech_config=self.speech_config, 
                audio_config=audio_config
            )
            
            def handle_result(evt):
                if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    if evt.result.text.strip():
                        print(f"识别到语音: {evt.result.text}")
                        ai_response = self.get_ai_response(evt.result.text)
                        print(f"AI回复: {ai_response}")
                        self.text_to_speech(ai_response)
            
            self.speech_recognizer.recognized.connect(handle_result)
            self.speech_recognizer.start_continuous_recognition()
            self.is_recognizing = True
            print("语音识别已启动")
            
        except Exception as e:
            print(f"启动语音识别出错: {str(e)}")
            self.stop_stream_recognition()
    
    def stop_stream_recognition(self):
        if self.speech_recognizer and self.is_recognizing:
            self.speech_recognizer.stop_continuous_recognition()
            self.is_recognizing = False
        if self.push_stream:
            self.push_stream.close()
        self.push_stream = None
        self.speech_recognizer = None
    
    def on_message(self, client, userdata, msg):
        if msg.topic == "voice/stream":
            try:
                if msg.payload == b"END_OF_STREAM":
                    self.stop_stream_recognition()
                    return
                
                if not self.is_recognizing:
                    self.start_stream_recognition()
                
                if self.push_stream:
                    self.push_stream.write(msg.payload)
                
            except Exception as e:
                print(f"处理音频出错: {str(e)}")
                self.stop_stream_recognition()

    def get_ai_response(self, message):
        max_retries = 3
        timeout = 10  # 设置10秒超时
        
        for attempt in range(max_retries):
            try:
                print(f"正在请求AI回复... (尝试 {attempt + 1}/{max_retries})")
                response = self.ai_client.chat.completions.create(
                    model="claude-3-5-haiku-20241022",
                    messages=[
                        {"role": "system", "content": "你是一个简洁友好的AI助手，回答要简短精确。"},
                        {"role": "user", "content": message}
                    ],
                    timeout=timeout
                )
                return response.choices[0].message.content
                
            except Exception as e:
                print(f"AI调用出错 (尝试 {attempt + 1}): {str(e)}")
                if attempt == max_retries - 1:  # 最后一次尝试
                    return "抱歉,我现在无法回答。请稍后再试。"
                else:
                    print("正在重试...")
                    time.sleep(1)  # 等待1秒后重试

    def text_to_speech(self, text):
        synthesizer = None
        try:
            print("正在生成语音...")
            speech_config = speechsdk.SpeechConfig(
                subscription=os.getenv('SPEECH_KEY'), 
                region=os.getenv('SPEECH_REGION')
            )
            
            # 设置语音合成参数
            speech_config.speech_synthesis_voice_name = "zh-CN-XiaoxiaoNeural"
            # 使用标准的 WAV 格式
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
            )
            
            # 创建音频配置 - 移除不必要的音频输出配置
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=speech_config,
                audio_config=None  # 不使用音频输出设备
            )
            
            # 执行语音合成
            result = synthesizer.speak_text_async(text).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                # 获取音频数据
                audio_data = result.audio_data
                
                # 创建 WAV 文件格式
                wav_stream = io.BytesIO()
                with wave.open(wav_stream, 'wb') as wav_file:
                    wav_file.setnchannels(1)  # 单声道
                    wav_file.setsampwidth(2)  # 16位采样
                    wav_file.setframerate(16000)  # 16kHz 采样率
                    wav_file.writeframes(audio_data)
                
                # 获取完整的 WAV 数据
                wav_data = wav_stream.getvalue()
                print(f"音频合成完成，数据大小: {len(wav_data)} 字节")
                
                # 发送音频数据
                result = self.mqtt_client.publish("voice/response", wav_data)
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    print("语音回复已发送")
                else:
                    print(f"发送失败，错误码: {result.rc}")
                
        except Exception as e:
            print(f"语��合成错误: {str(e)}")
        finally:
            if synthesizer:
                del synthesizer

    def start(self):
        mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
        mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
        
        self.mqtt_client.connect(mqtt_broker, mqtt_port)
        self.mqtt_client.loop_forever()

    def stop(self):
        self.stop_stream_recognition()
        self.mqtt_client.disconnect()

if __name__ == "__main__":
    chatbot = VoiceAIChatbot()
    try:
        chatbot.start()
    except KeyboardInterrupt:
        chatbot.stop() 