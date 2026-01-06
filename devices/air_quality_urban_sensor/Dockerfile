FROM python:3.9-slim
RUN pip install pandas paho-mqtt
COPY urban_sensor.py /urban_sensor.py
CMD ["python3", "-u", "/urban_sensor.py"]
