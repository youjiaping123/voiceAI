import paho.mqtt.client as mqtt
import os 
import wave
import pyaudio
from dotenv import load_dotenv
import msvcrt
import time

load_dotenv()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("成功连接到MQTT服务器")
        print(f"Client ID: {client._client_id}")
        print("正在订阅 voice/response 主题...")
        result = client.subscribe("voice/response")
        print(f"订阅结果: {result}")
        print("已订阅 voice/response 主题")
    else:
        print(f"连接失败，返回码: {rc}")

def record_audio():
    """录制音频
    Returns:
        bytes: 音频数据
    """
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000

    p = pyaudio.PyAudio()
    print("按下空格键开始录音，再次按下空格键结束...")

    stream = p.open(format=FORMAT,
                   channels=CHANNELS,
                   rate=RATE,
                   input=True,
                   frames_per_buffer=CHUNK)

    frames = []
     
    # 清空键盘缓冲区
    while msvcrt.kbhit():
        msvcrt.getch()
    
    # 等待空格键按下开始录音
    while True:
        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key == b' ':  # 空格键
                print("开始录音...")
                break
            elif key == b'\x03':  # Ctrl+C
                raise KeyboardInterrupt
    
    # 录音直到再次按下空格键
    recording = True
    while recording:
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)
        
        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key == b' ':  # 再次按下空格键
                recording = False
            elif key == b'\x03':  # Ctrl+C
                raise KeyboardInterrupt

    print("录音结束")
    stream.stop_stream()
    stream.close()
    p.terminate()

    if len(frames) < 10:  # 如果录音时间太短（约0.3秒）
        print("录音时间太短")
        return None

    try:
        # 将音频数据转换为WAV格式
        with wave.open('temp.wav', 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))
        
        print("临时WAV文件已创建")
        
        # 读取WAV文件
        with open('temp.wav', 'rb') as f:
            audio_data = f.read()
        
        print(f"读取到的音频文件大小: {len(audio_data)} 字节")
        print(f"音频格式信息: 通道数={CHANNELS}, 采样率={RATE}")
        
        # 删除临时文件
        os.remove('temp.wav')
        print("临时WAV文件已删除")
        
        return audio_data
    except Exception as e:
        print(f"处理音频数据时出错: {str(e)}")
        return None

def send_audio(audio_data):
    print(f"准备发送音频数据，大小: {len(audio_data)} 字节")
    try:
        result = client.publish("voice/audio", audio_data)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print("音频数据已成功发送")
            print(f"消息ID: {result.mid}")
            # 等待消息发送完成
            result.wait_for_publish()
            print("消息发送已完成")
        else:
            print(f"音频数据发送失败，错误码: {result.rc}")
    except Exception as e:
        print(f"发送过程中出错: {str(e)}")

def on_message(client, userdata, msg):
    print(f"收到消息，主题: {msg.topic}")
    print(f"消息大小: {len(msg.payload)} 字节")
    
    if msg.topic == "voice/response":
        try:
            print("开始处理接收到的音频数据...")
            # 将接收到的音频数据保存为临时WAV文件
            temp_wav = 'received_response.wav'
            with open(temp_wav, 'wb') as f:
                f.write(msg.payload)
            print(f"音频数据已保存到临时文件: {temp_wav}")
            
            # 播放音频
            print("开始播放音频...")
            wf = wave.open(temp_wav, 'rb')
            p = pyaudio.PyAudio()
            stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                            channels=wf.getnchannels(),
                            rate=wf.getframerate(),
                            output=True)
            
            data = wf.readframes(1024)
            while data:
                stream.write(data)
                data = wf.readframes(1024)
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            wf.close()
            
            # 删除临时文件
            os.remove(temp_wav)
            print("音频播放完成，临时文件已删除")
        except Exception as e:
            print(f"播放音频时出错: {str(e)}")
            print(f"错误类型: {type(e)}")
            import traceback
            print(traceback.format_exc())

if __name__ == "__main__":
    # 创建MQTT客户端，指定使用 MQTT v3.1.1 协议
    client = mqtt.Client(protocol=mqtt.MQTTv311)
    client.on_connect = on_connect
    client.on_message = on_message
    
    # 启用调试日志
    client.enable_logger()
    
    # 连接到MQTT服务器
    mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
    mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
    
    print(f"正在连接到MQTT服务器 {mqtt_broker}:{mqtt_port}")
    try:
        client.connect(mqtt_broker, mqtt_port)
        print("MQTT连接已建立")
    except Exception as e:
        print(f"MQTT连接失败: {str(e)}")
    
    # 启动MQTT客户端循环
    client.loop_start()
    
    try:
        print("程序已启动，按 Ctrl+C 退出")
        while True:
            try:
                audio_data = record_audio()
                if audio_data:
                    send_audio(audio_data)
            except KeyboardInterrupt:
                print("\n程序正在退出...")
                break
    finally:
        client.loop_stop()
        client.disconnect()
        print("程序已终止")