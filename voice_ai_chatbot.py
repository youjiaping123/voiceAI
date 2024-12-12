import paho.mqtt.client as mqtt
import json
import azure.cognitiveservices.speech as speechsdk
import io
from openai import OpenAI
from dotenv import load_dotenv
import os
import wave
import time
import socket
import base64

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
        
        # 配置 OpenAI
        self.ai_client = OpenAI(
            api_key=os.getenv("API_KEY"),
            base_url=os.getenv("BASE_URL")
        )
        
        # MQTT客户端设置
        self.mqtt_client = mqtt.Client(protocol=mqtt.MQTTv311)
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        
        # UDP 服务器设置
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind(('0.0.0.0', 12345))
        
    def on_connect(self, client, userdata, flags, rc):
        print("语音AI聊天机器人已连接")
        client.subscribe("voice/audio")  # 订阅音频数据主题
        
    def on_message(self, client, userdata, msg):
        if msg.topic == "voice/audio":
            try:
                # 1. 语音识别
                audio_data = msg.payload
                text = self.speech_to_text(audio_data)
                
                if text:
                    print(f"识别到的文本: {text}")
                    # 2. 获取AI响应并转换为语音
                    self.process_ai_response(text)
            except Exception as e:
                print(f"处理音频数据时出错: {str(e)}")

    def process_ai_response(self, text):
        try:
            print("\n=== 开始处理AI响应 ===")
            # 配置语音合成
            speech_config = speechsdk.SpeechConfig(
                subscription=os.getenv('SPEECH_KEY'), 
                region=os.getenv('SPEECH_REGION')
            )
            speech_config.speech_synthesis_voice_name = "zh-CN-YunzeNeural"
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)

            # 获取AI响应
            print("正在获取AI响应...")
            response = self.ai_client.chat.completions.create(
                model="claude-3-5-haiku-20241022",
                messages=[
                    {"role": "system", "content": "..."},
                    {"role": "user", "content": text}
                ]
            )
            
            ai_text = response.choices[0].message.content
            print(f"AI响应文本: {ai_text}")

            # 语音合成
            result = synthesizer.speak_text_async(ai_text).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                # 将二进制音频数据转换为base64字符串
                audio_base64 = base64.b64encode(result.audio_data).decode('utf-8')
                
                audio_package = {
                    'is_final': True,
                    'audio_data': audio_base64,
                    'text': ai_text,
                    'segment_id': 1
                }
                
                # 发送响应
                self.mqtt_client.publish(
                    "voice/response/stream", 
                    json.dumps(audio_package)
                )
                print("响应已发送")
            else:
                print(f"语音合成失败: {result.reason}")
                
        except Exception as e:
            print(f"\n!!! 处理错误 !!!")
            print(f"错误类型: {type(e)}")
            print(f"错误信息: {str(e)}")
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
            
    def start(self):
        # 连接到MQTT服务器
        mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
        mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
        
        print(f"正在连接到MQTT服务器 {mqtt_broker}:{mqtt_port}")
        self.mqtt_client.connect(mqtt_broker, mqtt_port)
        self.mqtt_client.loop_forever()

    def start_udp_server(self):
        while True:
            data, addr = self.udp_socket.recvfrom(65507)  # UDP包最大大小
            # 处理接收到的音频数据
            self.process_audio_data(data, addr)
            
    def process_audio_data(self, audio_data, client_addr):
        text = self.speech_to_text(audio_data)
        if text:
            response = self.get_ai_response(text)
            audio_response = self.text_to_speech(response)
            
            # 分包发送音频数据
            chunk_size = 65507
            for i in range(0, len(audio_response), chunk_size):
                chunk = audio_response[i:i + chunk_size]
                self.udp_socket.sendto(chunk, client_addr)

if __name__ == "__main__":
    chatbot = VoiceAIChatbot()
    chatbot.start() 