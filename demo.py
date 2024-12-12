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
        
    def on_connect(self, client, userdata, flags, rc):
        print(f"语音AI聊天机器人已连接，返回码: {rc}")
        print(f"Client ID: {client._client_id}")
        result = client.subscribe("voice/audio")
        print(f"订阅 voice/audio 主题结果: {result}")
        
    def on_message(self, client, userdata, msg):
        if msg.topic == "voice/audio":
            print(f"收到音频数据，大小: {len(msg.payload)} 字节")
            try:
                # 处理接收到的音频数据
                audio_data = msg.payload
                text = self.speech_to_text(audio_data)
                if text:
                    print(f"识别到的文本: {text}")
                    ai_response = self.get_ai_response(text)
                    print(f"AI回复: {ai_response}")
                    self.text_to_speech(ai_response)
            except Exception as e:
                print(f"处理音频数据时出错: {str(e)}")
                import traceback
                print(traceback.format_exc())
                
    def speech_to_text(self, audio_data):
        try:
            # 将接收到的音频数据保存为临时WAV文件
            temp_wav = 'temp_audio.wav'
            print("开始写入音频数据到临时文件...")
            with open(temp_wav, 'wb') as f:
                f.write(audio_data)
            print("音频数据已写入临时文件。")
            
            # 创建音频配置
            print("创建音频配置...")
            audio_config = speechsdk.audio.AudioConfig(filename=temp_wav)
            
            # 创建语音识别器
            print("创建语音识别器...")
            speech_recognizer = speechsdk.SpeechRecognizer(
                speech_config=self.speech_config, 
                audio_config=audio_config
            )
            
            # 执行一次性识别
            print("开始语音识别...")
            result = speech_recognizer.recognize_once()
            print("语音识别完成。")
            
            # 确保在识别完成后删除临时文件
            print("释放音频配置并删除临时文件...")
            speech_recognizer = None  # 释放语音识别器对文件的占用
            audio_config = None  # 释放音频配置对文件的占用
            os.remove(temp_wav)
            print("临时文件已删除。")
            
            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                print(f"识别结果: {result.text}")
                return result.text
            else:
                print(f"无法识别语音: {result.reason}")
                return None
                
        except Exception as e:
            print(f"语音识别错误: {str(e)}")
            return None
            
    def get_ai_response(self, message):
        try:
            response = self.ai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "你是一个友好的助手。"},
                    {"role": "user", "content": message}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"调用 AI API 出错: {str(e)}")
            return "抱歉，我现在无法回答。"
            
    def text_to_speech(self, text):
        temp_wav = 'ai_response.wav'
        synthesizer = None
        try:
            print("开始生成AI回复音频...")
            
            # 配置语音合成
            speech_config = speechsdk.SpeechConfig(
                subscription=os.getenv('SPEECH_KEY'), 
                region=os.getenv('SPEECH_REGION')
            )
            
            speech_config.speech_synthesis_voice_name = "zh-CN-XiaoxiaoNeural"
            audio_config = speechsdk.audio.AudioOutputConfig(filename=temp_wav)
            
            # 创建语音合成器
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=speech_config, 
                audio_config=audio_config
            )
            
            # 执行语音合成
            result = synthesizer.speak_text_async(text).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                print(f"音频已保存到临时文件: {temp_wav}")
                
                # 释放合成器资源
                synthesizer = None
                
                # 读取音频文件并发布到MQTT
                with open(temp_wav, 'rb') as f:
                    audio_data = f.read()
                print(f"读取到的音频数据大小: {len(audio_data)} 字节")
                
                # 发布音频数据
                result = self.mqtt_client.publish("voice/response", audio_data)
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    print("MQTT发布成功")
                else:
                    print(f"MQTT发布失败，错误码: {result.rc}")
            else:
                print(f"语音合成失败: {result.reason}")
                
        except Exception as e:
            print(f"语音合成错误: {str(e)}")
            print(f"错误类型: {type(e)}")
            import traceback
            print(traceback.format_exc())
        
        finally:
            # 确保释放合成器
            if synthesizer:
                synthesizer = None
            
            # 等待一小段时间确保文件被释放
            time.sleep(0.5)
            
            # 尝试删除临时文件
            try:
                if os.path.exists(temp_wav):
                    os.remove(temp_wav)
                    print("临时音频文件已删除")
            except Exception as e:
                print(f"删除临时文件时出错: {str(e)}")
            
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