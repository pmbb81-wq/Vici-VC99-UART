from PyQt5.QtCore import QObject, pyqtSignal, QIODevice
from PyQt5.QtSerialPort import QSerialPort

class SerialDevice(QObject):
    frameReceived = pyqtSignal(bytes)
    errorOccurred = pyqtSignal(str)
    connectedChanged = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._port = QSerialPort(self)
        self._buffer = bytearray()
        self._port.readyRead.connect(self.on_ready_read)
        self._port.errorOccurred.connect(lambda e: self.errorOccurred.emit(self._port.errorString()))
    
    def open(self, port_name, baud=2400):
        if self._port.isOpen():
            self._port.close()
        
        self._port.setPortName(port_name)
        self._port.setBaudRate(baud)
        self._port.setDataBits(QSerialPort.Data8)
        self._port.setParity(QSerialPort.NoParity)
        self._port.setStopBits(QSerialPort.OneStop)
        self._port.setFlowControl(QSerialPort.NoFlowControl)
        
        if self._port.open(QIODevice.ReadOnly):
            self._buffer.clear()
            self.connectedChanged.emit(True)
            return True
        else:
            self.connectedChanged.emit(False)
            self.errorOccurred.emit(self._port.errorString())
            return False
    
    def close(self):
        if self._port.isOpen():
            self._port.close()
        self._buffer.clear()
        self.connectedChanged.emit(False)
    
    def is_open(self):
        return self._port.isOpen()
    
    def error_string(self):
        return self._port.errorString()
    
    def on_ready_read(self):
        data = self._port.readAll().data()
        self._buffer.extend(data)
        
        while True:
            idx = self._buffer.find(b'\r\n')
            if idx < 0:
                break
            frame = bytes(self._buffer[0:idx+2])
            del self._buffer[0:idx+2]
            if len(frame) == 14:
                self.frameReceived.emit(frame)
        
        if len(self._buffer) > 256:
            self._buffer.clear()
