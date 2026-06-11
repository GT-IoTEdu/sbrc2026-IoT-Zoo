FROM python:3.9-slim
RUN pip install pandas paho-mqtt eclipse-zenoh==1.7.2
COPY urban_sensor.py /urban_sensor.py
COPY urban_sensor_zenoh.py /urban_sensor_zenoh.py
COPY iotzoo_zenoh.py /iotzoo_zenoh.py
CMD ["python3", "-u", "/urban_sensor.py"]
