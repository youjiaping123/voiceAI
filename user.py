import paho.mqtt.client as mqtt  # MQTT客户端库
import os 
import wave  # 用于处理WAV音频文件
import pyaudio  # 用于音频录制和播放
from dotenv import load_dotenv  # 环境变量加载
import msvcrt  # Windows控制台输入
import time

# 加载环境变量
load_dotenv()

def on_connect(client, userdata, flags, rc):
    """MQTT连接成功的回调函数"""
    if rc == 0:
        print("成功连接到MQTT服务器")
        print(f"Client ID: {client._client_id}")
        print("正在订阅 voice/response 主题...")
        result = client.subscribe("voice/response")
        print(f"订阅结果: {result}")
        print("已订阅 voice/response 主题")
    else:
        print(f"连接失败，返回码: {rc}")

def record_and_stream_audio(client):
    """实时录制并发送音频流的函数"""
    # 设置音频参数
    CHUNK = 1024  # 每次读取的音频块大小
    FORMAT = pyaudio.paInt16  # 16位音频格式
    CHANNELS = 1  # 单声道
    RATE = 16000  # 采样率16kHz

    # 初始化PyAudio
    p = pyaudio.PyAudio()
    print("按下空格键开始录音，再次按下空格键结束...")

    # 打开音频输入流
    stream = p.open(format=FORMAT,
                   channels=CHANNELS,
                   rate=RATE,
                   input=True,
                   frames_per_buffer=CHUNK)

    # 清空键盘缓冲区
    while msvcrt.kbhit():
        msvcrt.getch()
    
    # 等待空格键按下开始录音
    while True:
        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key == b' ':  # 空格键
                print("开始录音和流式传输...")
                break
            elif key == b'\x03':  # Ctrl+C
                raise KeyboardInterrupt
    
    # 录音并实时发送
    recording = True
    while recording:
        try:
            # 读取音频数据
            data = stream.read(CHUNK, exception_on_overflow=False)
            
            # 发送音频数据
            result = client.publish("voice/stream", data)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                print(f"发送失败，错误码: {result.rc}")
            
            # 检查是否按下空格键结束录音
            if msvcrt.kbhit():
                key = msvcrt.getch()
                if key == b' ':  # 空格键
                    recording = False
                elif key == b'\x03':  # Ctrl+C
                    raise KeyboardInterrupt
                    
        except Exception as e:
            print(f"录音或发送过程中出错: {str(e)}")
            recording = False

    # 清理资源
    print("录音结束")
    stream.stop_stream()
    stream.close()
    p.terminate()

    # 发送结束标记
    client.publish("voice/stream", b"END_OF_STREAM")

def on_message(client, userdata, msg):
    """处理接收到的MQTT消息的回调函数"""
    print(f"收到消息，主题: {msg.topic}")
    print(f"消息大小: {len(msg.payload)} 字节")
    
    if msg.topic == "voice/response":
        try:
            print("开始处理接收到的音频数据...")
            # 保存接收到的音频数据为临时WAV文件
            temp_wav = 'received_response.wav'
            with open(temp_wav, 'wb') as f:
                f.write(msg.payload)
            print(f"音频数据已保存到临时文件: {temp_wav}")
            
            # 播放音频响应
            print("开始播放音频...")
            wf = wave.open(temp_wav, 'rb')
            p = pyaudio.PyAudio()
            stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                            channels=wf.getnchannels(),
                            rate=wf.getframerate(),
                            output=True)
            
            # 分块读取并播放音频
            data = wf.readframes(1024)
            while data:
                stream.write(data)
                data = wf.readframes(1024)
            
            # 清理资源
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
    # 创建MQTT客户端实例
    client = mqtt.Client(protocol=mqtt.MQTTv311)
    client.on_connect = on_connect
    client.on_message = on_message
    
    # 启用MQTT客户端调试日志
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
                record_and_stream_audio(client)
            except KeyboardInterrupt:
                print("\n程序正在退出...")
                break
    finally:
        # 清理资源并断开连接
        client.loop_stop()
        client.disconnect()
        print("程序已终止")