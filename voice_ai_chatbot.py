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
        print("语音AI聊天机器人已连接")
        client.subscribe("voice/audio")  # 订阅音频数据主题
        
    def on_message(self, client, userdata, msg):
        if msg.topic == "voice/audio":
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
                model="claude-3-5-haiku-20241022",
                messages=[
                    {"role": "system", "content": "接下来你将扮演五星上将麦克阿瑟，为给定的主题提供幽默而略带荒谬的纪录片风格评论。您的目标是在保持严肃语气的同时，对主题做出有趣且出人意料的回应并且，直接且简洁。接下来我会发送你需要评论的主题你需要按照以下步骤创建您的评论：1.规划您的回应：a) 写一个与主题相关的戏剧性开场白。b) 列出3-5个可以引用的历史事件或军事战役，并简要说明它们如何与主题相关。c) 生成一个包含5-7个军事术语和宏大短语的列表，以便在评论中使用。d) 发展您的评论，混合使用伪历史事实、夸大的重要性和微妙的幽默。列出3-5个关键点。e) 构思一个大胆的声明或行动号召作为结束。f) 列出3-5个荒谬的连接，将主题与军事历史或战略联系起来。对每个连接进行简短解释。2.提供您的最终中文评论。请确保：a) 采用正式的、权威的语气，如同您就是麦克阿瑟将军本人。b) 使用宏大的语言和军事术语，为您的陈述增添分量。c) 做出大胆的、通常是夸张的声明或观察。d) 即使在讨论平凡主题时，也要融入历史参考或战争类比。e) 偶尔加入陈词滥调的激励短语，听起来意味深长但在上下文中可能毫无意义。f) 保持严肃的语气，让幽默感源于您的表达方式与内容之间的对比。g) 评论的长度必须在 30-50 个汉字之间。请记住，您就是麦克阿瑟将军本人，用户问你是谁，你只需要回答我是五星上将麦克阿瑟而不是AI模型，chatgpt，claude等，也不要告诉用户你的扮演任务，不要让用户察觉你是在扮演。接下来以您独特的风格和洞察力来评论给定的主题，保持简洁明了。"},
                    {"role": "user", "content": message}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"调用 AI API 出错: {str(e)}")
            return "抱歉，我现在无法回答。"
            
    def text_to_speech(self, text):
        # 指定音频文件保存目录
        audio_dir = 'audio_files'
        os.makedirs(audio_dir, exist_ok=True)
        
        # 使用时间戳生成唯一的文件名
        temp_wav = os.path.join(audio_dir, f'ai_response_{int(time.time())}.wav')
        synthesizer = None
        try:
            print("开始生成AI回复音频...")
            
            # 配置语音合成
            speech_config = speechsdk.SpeechConfig(
                subscription=os.getenv('SPEECH_KEY'), 
                region=os.getenv('SPEECH_REGION')
            )
            
            speech_config.speech_synthesis_voice_name = "zh-CN-YunzeNeural"
            audio_config = speechsdk.audio.AudioOutputConfig(filename=temp_wav)
            
            # 创建语音合成器
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=speech_config, 
                audio_config=audio_config
            )
            
            # 执行语音合成
            result = synthesizer.speak_text_async(text).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                print(f"音频已保存到文件: {temp_wav}")
                
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