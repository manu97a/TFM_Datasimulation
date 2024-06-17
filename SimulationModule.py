import sys
import os
import pymongo
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QWidget,QMainWindow, QPushButton, QVBoxLayout,QSpinBox,QTableWidgetItem
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QDate, QTime, Qt

import random
import time
import datetime
import threading
import json
from datetime import datetime, timedelta

import paho.mqtt.client as mqtt

class MiVentana(QMainWindow):
    def __init__(self):
        super().__init__()
        loader = QUiLoader()
        self.ui = loader.load("InterfazGUI.ui")
        self.setCentralWidget(self.ui)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
       
        # self.ui.setFocusPolicy()
        # Conexion a base de datos para obtener actuadores
        self.client = pymongo.MongoClient("mongodb+srv://plataformaPMR:NT0RHvpfC0KMgbra@cluster0.cae2jjy.mongodb.net/platformtfm")
        self.db = self.client["platformtfm"]
        self.collection = self.db["actuadors"] 
        self.actuadores_db = self.collection.find()
        self.tab_actuadores = self.ui.findChild(QWidget,"tab_2") 
        self.estadoActuadoresDB =  {}
        self.layout_actuadores = QVBoxLayout(self.tab_actuadores)
        self.actuadores_db_estado = {}
        self.conectar_botones_actuadores()
        # Solicitar los datos de tiempo y fecha de la GUI
        self.fecha_simulacion_automatica =  QDate.currentDate()
        self.hora_simulacion_automatica = QTime.currentTime()
        time_object_simulacion_automatica = self.hora_simulacion_automatica.toString('HH:mm:ss')
        date_object_simulacion_automatica = self.fecha_simulacion_automatica.toString('dd-MM-yyyy')
        ventana_temporal_sa = date_object_simulacion_automatica + ' ' + time_object_simulacion_automatica
        self.tiempo_simulacion_automatica = datetime.strptime(ventana_temporal_sa,'%d-%m-%Y %H:%M:%S')
        # Establecer tiempo y fecha de simulacion automatica
        self.ui.timeEdit_2.setTime(self.hora_simulacion_automatica)
        self.ui.dateEdit_2.setDate(self.fecha_simulacion_automatica)
        # Conexion a base de datos para obtener datos de posicion
        self.collection_coordenadas = self.db["coordenadas"]
        self.coordenadas = list(self.collection_coordenadas.find())
        self.coordenadas_dict = {}
        # print(self.coordenadas)
        for coord in self.coordenadas:
            self.coordenadas_dict[coord['_id']] = {'x': coord['x'], 'y': coord['y']}
        # print(self.coordenadas_dict[0]['x']) imprime la coordenada en x 82.68478393554688
        self.ui.tableWidget.setRowCount(len(self.coordenadas))
        self.ui.tableWidget.setColumnCount(3)
        headers = ["_id", "x", "y"]
        self.ui.tableWidget.setHorizontalHeaderLabels(headers)
        for i, fila in enumerate(self.coordenadas):
            for j, valor in enumerate(["_id", "x", "y"]):
                item = QTableWidgetItem(str(fila.get(valor,"")))
                self.ui.tableWidget.setItem(i,j,item)


        # Conexion a base de datos para obtener luces
        self.tab_luces = self.ui.findChild(QWidget,"tab_3")
        self.collection_luces = self.db["luzs"]
        self.collection_general_data = self.db['simulation']
        self.collection_umbrales_salud = self.db['umbrales']
        self.luces_db = self.collection_luces.find()
        self.layout_luces = QVBoxLayout(self.tab_luces)
        self.luces_db_estado = {}
        self.estadoLucesDB = {} 
        self.conectar_botones_luces()
        # Conexion a base de datos para obtener sensores
        self.collection_sensores = self.db["sensors"]
        self.sensores_db = list(self.collection_sensores.find())
        # print("esto es sensores db",self.sensores_db)
        self.flag_iniciosensores = False
        
        # Valores de salud
        self.pulso = 0
        self.saturacion = 0
        self.acelerometro = 0
        self.flag_alteracion_pulso = False
        self.flag_alteracion_saturacion = False
        self.flag_alteracion_acelerometro = False
        # Archivo JSON
        self.identificador = 0
        self.ruta_base_datos = "/Users/manuco97/Documents/MAESTRIA CADIZ/TFM/Simulacion/QTDesigner/Plataforma/plataforma-pmr/json/datos.json"
        # Configuración MQTT
        self.broker_address = "test.mosquitto.org"  
        self.broker_port = 1883  
        self.simulacion_activa = False
        self.simulacion_automatica_activa = False
        # Cliente MQTT
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_publish = self.on_publish
        self.client.on_message = self.on_message
        self.client.connect(self.broker_address, self.broker_port, 60)
        self.client.loop_start()
    
        # Conectar señales y slots
        self.ui.pushButton_2.clicked.connect(self.inicio_simulacion)
        self.ui.pushButton.clicked.connect(self.detener_simulacion)
        # 
        self.ui.pushButton_4.clicked.connect(self.inicio_simulacion_automatica)
        ## Cambios de valores acelerometros
        self.ui.pushButton_17.clicked.connect(lambda: self.setFlag_alteracion("acelerometro"))
        ## Eliminar datos de simulacion
        self.ui.pushButton_3.clicked.connect(self.limpiardatos_simulacion)
        self.ui.pushButton_5.clicked.connect(self.limpiardatos_coordenadas)
        # Variables para control de movimiento
        self.posicionX = 0
        self.posicionY = 0 
        # Conteo de pasos
        self.contador_pasos = 0
        self.inicio_contador = False
        # Botones movimiento simulacion
        self.ui.pushButton_23.clicked.connect(self.mover_arriba)
        self.ui.pushButton_25.clicked.connect(self.mover_izquierda)
        self.ui.pushButton_26.clicked.connect(self.mover_derecha)
        self.ui.pushButton_27.clicked.connect(self.mover_abajo)
        # Botones establecer posicion de inicio
        self.ui.pushButton_29.clicked.connect(self.iniciar_entrada)
        self.ui.pushButton_28.clicked.connect(self.iniciar_dormitorio)
        self.ui.pushButton_31.clicked.connect(self.iniciar_banio)
        self.ui.pushButton_30.clicked.connect(self.iniciar_cocina)
        self.ui.pushButton_32.clicked.connect(self.iniciar_sala)
        # Alteracion valores de salud
        self.ui.pushButton_37.clicked.connect(lambda: self.setFlag_alteracion("pulso")) 
        self.ui.pushButton_39.clicked.connect(lambda: self.setFlag_alteracion("pulso")) 
        self.ui.pushButton_38.clicked.connect(lambda: self.setFlag_alteracion("saturacion")) 
        self.ui.pushButton_40.clicked.connect(lambda: self.setFlag_alteracion("saturacion")) 
    # Funciones para los actuadores
    def create_lambda(self, button,seleccion):
        if seleccion == 1: 
            def on_button_clicked():
                self.onPressed(button.text(),1)
            return on_button_clicked
        elif seleccion == 2:
            def on_button_clicked():
                self.onPressed(button.text(),2)
            return on_button_clicked

    def onPressed(self, name,seleccion):
        if seleccion == 1: 
            if self.estadoActuadoresDB[name] == 0:
                self.estadoActuadoresDB[name] = 1
                # print(self.estadoActuadoresDB)
            else:
                self.estadoActuadoresDB[name] = 0
                # print(self.estadoActuadoresDB)
        elif seleccion == 2:
            if self.estadoLucesDB[name]== 0:
                self.estadoLucesDB[name] = 1
            else:
                self.estadoLucesDB[name] = 0
    def conectar_botones_luces(self):
        for luz in self.luces_db:
            nombre_luz = luz["name"]
            boton = QPushButton(nombre_luz,self)
            self.layout_luces.addWidget(boton)
            self.estadoLucesDB[nombre_luz] = 0
            boton.clicked.connect(self.create_lambda(boton,2))


    def conectar_botones_actuadores(self):
        for actuador in self.actuadores_db:
            nombre_actuador = actuador["name"]
            boton = QPushButton(nombre_actuador, self)
            self.layout_actuadores.addWidget(boton)
            self.estadoActuadoresDB[nombre_actuador] = 0
            boton.clicked.connect(self.create_lambda(boton,1))  # Pasar el botón como argumento
    ## ---------------------------------------- ##
    
    # Funciones para simulacion de sensores
    def simularSensores(self):
        if (self.flag_iniciosensores):
            datos_diccionario = {}
            for sensor in self.sensores_db:
                sensorname = sensor['name']
                minValue = sensor['minValue']
                maxValue = sensor['maxValue']
                valor_simulado = random.randint(minValue, maxValue)
                datos_diccionario[sensorname] = valor_simulado
            return datos_diccionario


    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("Conexión exitosa con el servidor MQTT")
            # Suscribirse al tema "datos_basicos"
            self.client.subscribe("datos_basicos")
            self.client.subscribe("TFM_actuadores")
            self.client.subscribe("TFM_luces")
        else:
            print(f"Error de conexión. Código de retorno={rc}")

    def on_publish(self, client, userdata, mid):
        print("Publicación exitosa con mensaje ID:", mid)

    def on_message(self, client, userdata, message):
        topic = message.topic
        payload = json.loads(message.payload.decode("utf-8"))
        if topic == "TFM_actuadores":
            print(payload)
            for nombre_actuador, estado in payload.items():
                # Actualizar el estado del actuador específico
                self.estadoActuadoresDB[nombre_actuador] = estado
            
        if topic == "TFM_luces":
            for nombre_luz, estado in payload.items():
                self.estadoLucesDB[nombre_luz] = estado
            

    def inicio_simulacion(self):
        if not self.simulacion_activa:
            self.simulacion_activa = True
            with open(self.ruta_base_datos, 'w') as f:
                f.write("[]") 
            threading.Thread(target=self.crear_reloj).start()
            threading.Thread(target=self.reloj_pasos).start()
    def inicio_simulacion_automatica(self):
        if not self.simulacion_automatica_activa:
            self.simulacion_automatica_activa = True
            threading.Thread(target=self.reloj_simulacion_automatica).start()
            threading.Thread(target=self.enviodatos_simulacion_automatica).start()
    def valoresAleatorios(self):
        return random.randint(60, 100)
    def obtener_fechahora(self):
        # Fecha y Tiempo de simulacion
        fecha_simulacion_str =  self.ui.dateEdit.date().toString("dd-MM-yyyy")
        self.fecha_simulacion = fecha_simulacion_str
        hora_simulacion_str =   self.ui.timeEdit.time().toString("HH:mm:ss")
        temporal_completo = fecha_simulacion_str + ' ' + hora_simulacion_str
        self.tiempo_actual = datetime.strptime(temporal_completo, '%d-%m-%Y %H:%M:%S')
        self.tiempo_actual_pasos = datetime.strptime(temporal_completo, '%d-%m-%Y %H:%M:%S')
    def fechahora_simulacion_automatica(self):
        self.actual_time_sim_automatica = self.hora_simulacion_automatica.toString("HH:mm:ss")
        self.fecha_simulacion_automatica = self.fecha_simulacion_automatica.toString("dd-MM-yyyy")
        self.tiempo_completo_sim_automatica = self.fecha_simulacion_automatica + ' ' + self.actual_time_sim_automatica
        self.tiempo_actual = datetime.strptime(self.tiempo_completo_sim_automatica,'%d-%m-%Y %H:%M:%S')
    # def reloj_simulacion_automatica(self):
    #     self.actual_time_sim_automatica = self.hora_simulacion_automatica.toString("HH:mm:ss")
    #     self.fecha_simulacion_automatica = self.fecha_simulacion_automatica.toString("dd-MM-yyyy")
    #     self.tiempo_completo_sim_automatica = self.fecha_simulacion_automatica + ' ' + self.actual_time_sim_automatica
    #     self.tiempo_actual = datetime.strptime(self.tiempo_completo_sim_automatica,'%d-%m-%Y %H:%M:%S')
    #     self.flag_movimiento = False
    #     # Parametros de movimiento
    #     velocidad = 5
    #     distancia_total = self.calculo_distancia(self.coordenadas_dict[0],self.coordenadas_dict[1])
    #     tiempo_total = distancia_total / velocidad
    #     intervalos_tiempo = int(tiempo_total / 10)
    #     while self.simulacion_automatica_activa:
    #         for i in range(len(self.coordenadas_dict)):
    #             # Si no es la última coordenada
    #             if i < len(self.coordenadas_dict) - 1:
    #                 coordenada_actual = self.coordenadas_dict[i]
    #                 coordenada_siguiente = self.coordenadas_dict[i + 1]
    #                 # Calcular distancia, tiempo total e intervalos de tiempo
    #                 distancia_total = self.calculo_distancia(coordenada_actual, coordenada_siguiente)
    #                 tiempo_total = distancia_total / velocidad
    #                 intervalos_tiempo = int(tiempo_total / 10)
    #                 # Recorrer los intervalos de tiempo
    #                 for j in range(intervalos_tiempo + 1):
    #                     # Calcular las coordenadas en el tiempo actual
    #                     fraccion_tiempo = j / intervalos_tiempo
    #                     coord_X_actual  = coordenada_actual['x'] + (coordenada_siguiente['x'] - coordenada_actual['x'] ) * fraccion_tiempo
    #                     coord_Y_actual  = coordenada_actual['y'] + (coordenada_siguiente['y'] - coordenada_actual['y'] ) * fraccion_tiempo
    #                     # Publicar las coordenadas, el tiempo y la posición
    #                     print("Coordenadas en el tiempo", i * 10 + j, "segundos:", coord_X_actual, coord_Y_actual)
    #                     self.posicion_mensaje = {'x': coord_X_actual,'y': coord_Y_actual,}
    #                     posicion_json = json.dumps(self.posicion_mensaje)
    #                     self.client.publish("TFM_ubicacion",posicion_json, qos=1)
    #                     self.tiempo_actual += timedelta(seconds=5)
    #                     self.client.publish("TFM_Tiempo",self.tiempo_actual.strftime("%Y-%m-%d %H:%M:%S"),qos=1)
    #                     time.sleep(5)
    #         self.simulacion_automatica_activa = False
    #         if (not self.simulacion_automatica_activa):
    #             self.client.loop_stop()
    #             self.client.disconnect()
    #             print("Cliente MQTT desconectado")    
    #             break
    def reloj_simulacion_automatica(self):
        
        self.flag_movimiento = False
        # Parametros de movimiento
        velocidad = 5
        i = 0  # Índice para recorrer las coordenadas
        while self.simulacion_automatica_activa:
            # Si no es la última coordenada
            if i < len(self.coordenadas_dict) - 1:
                coordenada_actual = self.coordenadas_dict[i]
                coordenada_siguiente = self.coordenadas_dict[i + 1]
                # Calcular distancia, tiempo total e intervalos de tiempo
                distancia_total = self.calculo_distancia(coordenada_actual, coordenada_siguiente)
                tiempo_total = distancia_total / velocidad
                intervalos_tiempo = int(tiempo_total / 10)
                # Recorrer los intervalos de tiempo
                for j in range(intervalos_tiempo + 1):
                    # Calcular las coordenadas en el tiempo actual
                    fraccion_tiempo = j / intervalos_tiempo
                    coord_X_actual  = coordenada_actual['x'] + (coordenada_siguiente['x'] - coordenada_actual['x'] ) * fraccion_tiempo
                    coord_Y_actual  = coordenada_actual['y'] + (coordenada_siguiente['y'] - coordenada_actual['y'] ) * fraccion_tiempo
                    # Publicar las coordenadas, el tiempo y la posición
                    print("Coordenadas en el tiempo", i * 10 + j, "segundos:", coord_X_actual, coord_Y_actual)
                    self.posicion_mensaje = {'x': coord_X_actual,'y': coord_Y_actual,}
                    posicion_json = json.dumps(self.posicion_mensaje)
                    self.client.publish("TFM_ubicacion",posicion_json, qos=1)
                    self.tiempo_simulacion_automatica += timedelta(seconds=5)
                    # self.client.publish("TFM_Tiempo",self.tiempo_simulacion_automatica.strftime("%Y-%m-%d %H:%M:%S"),qos=1)
                    time.sleep(5)
            else:
                self.simulacion_automatica_activa = False
                break
            i += 1
        
        if not self.simulacion_automatica_activa:
            self.client.loop_stop()
            self.client.disconnect()
            print("Cliente MQTT desconectado")


    def enviodatos_simulacion_automatica(self):
        try:
            time_AS = self.tiempo_simulacion_automatica
            print(time_AS)
            self.flag_iniciosensores = True
            while self.simulacion_automatica_activa:
                if (self.flag_alteracion_pulso):
                    print(self.flag_alteracion_pulso)

                    self.pulso = self.alterar_pulso()
                    print(self.pulso)
                else:    
                    self.pulso = self.valores_pulso()
                if (self.flag_alteracion_saturacion):
                    self.saturacion = self.alterar_saturacion()
                else:
                    self.saturacion = self.valores_saturacion()
                if (self.flag_alteracion_acelerometro):
                    self.acelerometro =  self.alterar_acelerometro()
                else:
                    self.acelerometro = self.valores_acelerometro()
                mensaje = {
                    'pulso': self.pulso,
                    'saturacion': self.saturacion,
                    'acelerometro': self.acelerometro
                }
                mensaje_json = json.dumps(mensaje)
                self.client.publish("TFM_Salud", mensaje_json,qos=1)
                print("EstadoActuadores:",self.estadoActuadoresDB)
                actuadores_json = json.dumps(self.estadoActuadoresDB)
                self.client.publish("TFM_actuadores", actuadores_json ,qos=1)
                # Estado Luces
                self.sensorica = self.simularSensores()
                print(self.sensorica)
                self.client.publish("TFM_Sensores",json.dumps(self.sensorica),qos=1)

                print("EstadoLuces:",self.estadoLucesDB)
                luces_json = json.dumps(self.estadoLucesDB)
                self.client.publish("TFM_luces",luces_json,qos=1)
                self.client.publish("TFM_Tiempo",time_AS.strftime("%Y-%m-%d %H:%M:%S"),qos=1)
                data_database = {
                    "Luces": self.estadoLucesDB,
                    "Actuadores": self.estadoActuadoresDB,
                    "Sensores": self.sensorica,
                    "Salud:" : mensaje,
                    "time": time_AS.strftime("%Y-%m-%d %H:%M:%S")
                }
                self.collection_general_data.insert_one(data_database)
                time_AS += timedelta(seconds=5)
                time.sleep(5)
        finally:
            self.client.loop_stop()
            self.client.disconnect()
            print("Cliente MQTT desconectado")   
        

    def calculo_distancia(self,punto1, punto2):
        distancia_x = punto2['x'] - punto1['x']
        distancia_y = punto2['y'] - punto1['y']
        distancia_total = (distancia_x ** 2 + distancia_y ** 2) ** 0.5
        return distancia_total
    def calcular_posicion_intermedia(self, punto1, punto2, t):
        return {
            'x': punto1['x'] + (punto2['x'] - punto1['x']) * t,
            'y': punto1['y'] + (punto2['y'] - punto1['y']) * t,
        }
    def reloj_pasos(self):
        try:
            self.obtener_fechahora()
            while self.simulacion_activa:
                tiempo_actual_str = self.tiempo_actual_pasos.strftime("%H:%M:%S")
                # Enviar posicion de persona en casa a broker MQTT 
                # Mensaje ubicacion
                self.posicion_mensaje = {
                    'x': self.posicionX,
                    'y': self.posicionY,
                }
                posicion_json = json.dumps(self.posicion_mensaje)
                # print(posicion_json)
                self.client.publish("TFM_ubicacion",posicion_json, qos=1)
                # TODO: Enviar cantidad de pasos
                # ------------------------------ #
                # Estado actuadores
                print("EstadoActuadores:",self.estadoActuadoresDB)
                actuadores_json = json.dumps(self.estadoActuadoresDB)
                self.client.publish("TFM_actuadores", actuadores_json ,qos=1)
                # Estado Luces
                print("EstadoLuces:",self.estadoLucesDB)
                luces_json = json.dumps(self.estadoLucesDB)
                self.client.publish("TFM_luces",luces_json,qos=1)
                # Actualizador contador y tiempo
                self.tiempo_actual_pasos += timedelta(seconds=1)
                time.sleep(1)

        finally:
            self.client.loop_stop()
            self.client.disconnect()
            print("Cliente MQTT desconectado")      

    

    
    def crear_reloj(self):
        try:
            self.obtener_fechahora()
            # Umbrales
            self.umbralPulso = self.ui.findChild(QSpinBox, "umbralPulso").value()
            self.umbralSaturacion = self.ui.findChild(QSpinBox, "umbralSaturacion").value()
            self.umbralAcelerometroCaida = self.ui.findChild(QSpinBox, "umbralAcelerometroCaida").value()
            self.umbralAcelerometroMovInv = self.ui.findChild(QSpinBox, "umbralAcelerometroMovInv").value()
            umbrales = {
                "pulso": self.umbralPulso,
                "saturacion": self.umbralSaturacion,
                "acelerometroCaida": self.umbralAcelerometroCaida,
                "acelerometroMovInv": self.umbralAcelerometroMovInv,
            }
            print(umbrales)
            self.collection_umbrales_salud.delete_many({})
            self.collection_umbrales_salud.insert_one(umbrales)
            database ={}
            self.flag_iniciosensores = True
            while self.simulacion_activa:
                tiempo_actual_str = self.tiempo_actual.strftime("%H:%M:%S")
                if (self.flag_alteracion_pulso):
                    print(self.flag_alteracion_pulso)

                    self.pulso = self.alterar_pulso()
                    print(self.pulso)
                else:    
                    self.pulso = self.valores_pulso()
                if (self.flag_alteracion_saturacion):
                    self.saturacion = self.alterar_saturacion()
                else:
                    self.saturacion = self.valores_saturacion()
                if (self.flag_alteracion_acelerometro):
                    self.acelerometro =  self.alterar_acelerometro()
                else:
                    self.acelerometro = self.valores_acelerometro()
                mensaje = {
                    'pulso': self.pulso,
                    'saturacion': self.saturacion,
                    'acelerometro': self.acelerometro
                }
                # Enviar mensaje por MQTT datos salud
                mensaje_json = json.dumps(mensaje)
                
                self.client.publish("TFM_Salud", mensaje_json,qos=1)
                self.client.publish("TFM_Tiempo",self.tiempo_actual.strftime("%Y-%m-%d %H:%M:%S"),qos=1)
                # ------------------------------ #
                
                # ------------------------------ #
                self.sensorica = self.simularSensores();
                print("Esto es sensoricA",self.sensorica)
                self.client.publish("TFM_Sensores",json.dumps(self.sensorica),qos=1)
                # Enviar a base de datos
                data_database = {
                    "Luces": self.estadoLucesDB,
                    "Actuadores": self.estadoActuadoresDB,
                    "Sensores": self.sensorica,
                    "Salud:" : mensaje,
                    "time": self.tiempo_actual.strftime("%Y-%m-%d %H:%M:%S")
                }
                self.collection_general_data.insert_one(data_database)
                # ACtualizador contador y tiempo
                # self.identificador += 1
                self.tiempo_actual += timedelta(seconds=5)
                time.sleep(5)
                # ------------------------------- #
        finally:
            self.client.loop_stop()
            self.client.disconnect()
            print("Cliente MQTT desconectado")

    
    def fecha_existe(self,fecha):
        with open(self.ruta_base_datos, "r") as f:
            data = json.load(f)
        return fecha in data    
    ## Generacion de valores para Pulso
    def alterar_pulso(self):
        return random.randint(110, 190)
    def valores_pulso(self):
        return random.randint(75, 100)
     ## Generacion de valores para Saturacion 
    def valores_saturacion(self):
        return random.randint(85, 100)
    def alterar_saturacion(self):
        return random.randint(60, 80)
    #-----------------------------------#
    ## Generacion de valores para Acelerometro 
    def valores_acelerometro(self):
        return random.randint(0, 100)
    def alterar_acelerometro(self):
        return random.randint(101, 200)
    #-----------------------------------#
    def setFlag_alteracion(self,case):
        if  case == "pulso":
            self.flag_alteracion_pulso = not self.flag_alteracion_pulso
        if case == "saturacion":
            self.flag_alteracion_saturacion = not self.flag_alteracion_saturacion
        if case == "acelerometro":
            self.flag_alteracion_acelerometro = not self.flag_alteracion_acelerometro
   
   
    # CAMBIAR ESTADO DE LUCES
    def cambiar_estado_luz(self, nombre_luz, boton, texto):
        if self.estado_luces[nombre_luz] == "Apagado":
            self.estado_luces[nombre_luz] = "Encendido"
            print(self.estado_luces)
            boton.setText("Apagar " + texto)
        else:
            self.estado_luces[nombre_luz] = "Apagado"
            boton.setText("Encender " + texto)
    # APAGAR TODAS LAS LUCES
    def apagar_luces(self):
        for luces in self.estado_luces:
            self.estado_luces[luces] = "Apagado"
    # ENCENDER TODAS LAS LUCES
    def encender_luces(self):
        for luces in self.estado_luces:
            self.estado_luces[luces] = "Encendido"
    # APAGAR ACTUADORES
    def encender_actuadores(self):
        for actuadores in self.estado_actuadores:
            self.estado_actuadores[actuadores] = "Encendido"
    def apagar_actuadores(self):
        for actuadores in self.estado_actuadores:
            self.estado_actuadores[actuadores] = "Apagado"
            
    # ELIMINAR INFORMACION SIMULACION ANTERIOR
    def limpiardatos_simulacion(self):
        coleccion = "simulation"

        self.db[coleccion].delete_many({})
        print("Se han eliminado todos los datos de la simulacion")
    def limpiardatos_coordenadas(self):
        coleccion = "coordenadas"
        self.db[coleccion].delete_many({})
        print("Se han eliminado todos los datos de coordenadas")
    # FUNCIONES PARA CONTROLAR MOVIMIENTO DE LA PERSONA
    def mover_arriba(self):
        self.inicio_contador = True
        self.posicionY -= 10
        # print(self.posicion_arriba)
    def mover_izquierda(self):
        self.inicio_contador = True
        self.posicionX -= 10
        # print(self.posicion_izquierda)
    def mover_derecha(self):
        self.inicio_contador = True
        self.posicionX += 10
        # print(self.posicion_derecha)
    def mover_abajo(self):
        self.inicio_contador = True
        self.posicionY += 10
        # print(self.posicion_abajo)
    # FUNCIONES PARA ESTABLECER POSICION DE INICIO SIMULACION
    def reiniciar_posicion(self):
        self.posicionX = 0
        self.posicionY = 0

    def iniciar_entrada(self):
        self.reiniciar_posicion()
        self.posicionX = 454.5
        self.posicionY = 41
        
    def iniciar_dormitorio(self):
        self.reiniciar_posicion()
        self.posicionX = 94.5
        self.posicionY = 112
        
    def iniciar_banio(self):
        self.reiniciar_posicion()
        self.posicionX = 76.5
        self.posicionY = 528
    def iniciar_cocina(self):
        self.reiniciar_posicion()
        self.posicionX = 628.5
        self.posicionY = 216
    def iniciar_sala(self):
        self.reiniciar_posicion()
        self.posicionX = 529.5
        self.posicionY = 608


    def detener_simulacion(self, event=None):
        self.simulacion_activa = False
        self.simulacion_automatica_activa = False
        print("Simulación Finalizada")
        if event:
            event.accept()

    def closeEvent(self, event):
        self.detener_simulacion()

def main():
    app = QApplication(sys.argv)
    ventana = MiVentana()
    ventana.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
