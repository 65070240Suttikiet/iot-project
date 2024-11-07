from smbus3 import SMBus
from rpi_lcd import LCD
import time
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
import paho.mqtt.client as mqtt
import json

# ตั้งค่า I2C และ LCD
bus = SMBus(1)
lcd = LCD(0x27)

# ตั้งค่า MQTT
mqttc = mqtt.Client()
mqttc.connect("mqtt-dashboard.com", 1883)

# ฟังก์ชันอ่านข้อมูลจากเซ็นเซอร์ SHT31
def readData():
    # ส่งคำสั่งอ่านข้อมูลจาก SHT31
    bus.write_i2c_block_data(0x44, 0x2C, [0x06])
    time.sleep(0.5)

    # อ่านข้อมูล 6 ไบต์ (ค่าอุณหภูมิและความชื้น)
    data = bus.read_i2c_block_data(0x44, 0x00, 6)

    # คำนวณอุณหภูมิและความชื้น
    temp = data[0] * 256 + data[1]
    cTemp = -45 + (175 * temp / 65535.0)
    humidity = 100 * (data[3] * 256 + data[4]) / 65535.0

    return cTemp, humidity

# โหลดข้อมูลจากไฟล์ CSV สำหรับฝึกโมเดล
all_data = pd.read_csv('data_watering.csv')
data = {
    'temperature': all_data["Temp.(C)"],
    'humidity': all_data["Humi.(%)"],
    'watering': all_data["watering.(1/0)"].apply(lambda x: 1 if x > 0 else 0)
}

# สร้าง DataFrame และกำหนดฟีเจอร์ X และ label y
df = pd.DataFrame(data)
x = df[['temperature', 'humidity']]
y = df['watering']

# แบ่งข้อมูล train/test และฝึกโมเดล Logistic Regression
x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.2, random_state=42)
model = LogisticRegression()
model.fit(x_train, y_train)

# ตรวจสอบความแม่นยำของโมเดล
predictions = model.predict(x_test)
accuracy = accuracy_score(y_test, predictions)
print(f"Accuracy: {accuracy * 100:.2f}%")

# ฟังก์ชันทำนายว่าจะต้องรดน้ำต้นไม้หรือไม่จากค่าอุณหภูมิและความชื้น
def should_water_plants(temperature, humidity):
    new_data = pd.DataFrame([[temperature, humidity]], columns=['temperature', 'humidity'])
    water_prediction = model.predict(new_data)
    return "Watering Plants" if water_prediction[0] == 1 else "No Watering Plants"

# แสดงข้อความเริ่มต้นบน LCD
lcd.text("Dear,AJ Panwit<3", 1)
time.sleep(2)

# ลูปหลักในการอ่านค่าและแสดงผลบน LCD และส่งไปที่ MQTT
while True:
    # อ่านข้อมูลจากเซ็นเซอร์
    cTemp, humidity = readData()

    # แสดงค่าอุณหภูมิบนบรรทัดแรกของ LCD
    lcd.text(f"Temp: {cTemp:.2f} C", 1)

    # แสดงค่าความชื้นบนบรรทัดที่สองของ LCD
    lcd.text(f"Humidity: {humidity:.2f}%", 2)
    time.sleep(8)  # หน่วงเวลา 8 วินาทีสำหรับการแสดงข้อมูลอุณหภูมิและความชื้น

    # ใช้โมเดลในการทำนายว่ารดน้ำหรือไม่
    prediction = should_water_plants(cTemp, humidity)

    # แสดงเวลาและผลการทำนายบน LCD
    lcd.text(time.strftime('%d-%m-%Y %H:%M:%S'), 1)
    lcd.text(prediction, 2)

    # สร้าง payload สำหรับ MQTT โดยใช้ '|' เพื่อแยกข้อมูลและ '\n' สำหรับขึ้นบรรทัดใหม่
    mqtt_payload = (
        f"Prediction: {prediction} | Temperature: {cTemp:.2f} C | Humidity: {humidity:.2f}%\n"
        f"Timestamp: {time.strftime('%d-%m-%Y %H:%M:%S')}"
    )

    # ส่ง payload ไปยัง MQTT topic "sensor/data"
    mqttc.publish("sensor/tigerdata", mqtt_payload)

    # หน่วงเวลา 11 วินาทีก่อนวนลูปไปอ่านค่าต่อไป
    time.sleep(11)
