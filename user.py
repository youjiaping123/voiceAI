import paho.mqtt.client as mqtt
import os 
import wave
import pyaudio
from dotenv import load_dotenv
import msvcrt
import tempfile

load_dotenv()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("已连接到MQTT服务器")
        client.subscribe("voice/response")

def record_and_stream_audio(client):
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000

    p = pyaudio.PyAudio()
    print("\n按空格键开始/停止录音...")

    stream = p.open(format=FORMAT,
                   channels=CHANNELS,
                   rate=RATE,
                   input=True,
                   frames_per_buffer=CHUNK)

    while msvcrt.kbhit():
        msvcrt.getch()
    
    while True:
        if msvcrt.kbhit() and msvcrt.getch() == b' ':
            break
    
    print("开始录音中...")
    recording = True
    while recording:
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            client.publish("voice/stream", data)
            
            if msvcrt.kbhit() and msvcrt.getch() == b' ':
                print("停止录音...")
                recording = False
                    
        except Exception as e:
            print(f"录音出错: {str(e)}")
            recording = False

    stream.stop_stream()
    stream.close()
    p.terminate()
    client.publish("voice/stream", b"END_OF_STREAM")
    print("录音结束\n")

def on_message(client, userdata, msg):
    if msg.topic == "voice/response":
        temp_file = None
        try:
            print("收到语音回复，正在播放...")
            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_file.write(msg.payload)
            temp_file.flush()
            temp_file.close()
            
            wf = wave.open(temp_file.name, 'rb')
            p = pyaudio.PyAudio()
            stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                          channels=wf.getnchannels(),
                          rate=wf.getframerate(),
                          output=True,
                          frames_per_buffer=1024)
            
            chunk_size = 1024
            data = wf.readframes(chunk_size)
            while len(data) > 0:
                stream.write(data)
                data = wf.readframes(chunk_size)
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            wf.close()
            
            print("播放完成")
            
        except Exception as e:
            print(f"播放音频出错: {str(e)}")
        finally:
            if temp_file:
                try:
                    os.unlink(temp_file.name)
                except Exception as e:
                    print(f"删除临时文件失败: {e}")

if __name__ == "__main__":
    client = mqtt.Client(protocol=mqtt.MQTTv311)
    client.on_connect = on_connect
    client.on_message = on_message
    
    mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
    mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
    
    client.connect(mqtt_broker, mqtt_port)
    client.loop_start()
    
    try:
        while True:
            record_and_stream_audio(client)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()