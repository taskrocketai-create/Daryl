/*
  hcsr04_distance.ino
  Reads the HC-SR04 ultrasonic sensor and streams distance readings over
  USB serial as: DIST:123.45\n   (centimeters)

  Wiring:
    HC-SR04 VCC -> Nano 5V
    HC-SR04 GND -> Nano GND
    HC-SR04 TRIG -> Nano D9
    HC-SR04 ECHO -> Nano D10  (use a voltage divider if your board is 3.3V-only;
                                 the Nano is 5V-tolerant so it's fine as-is)
*/

const int TRIG_PIN = 9;
const int ECHO_PIN = 10;

void setup() {
  Serial.begin(9600);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
}

void loop() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 30000); // 30ms timeout (~5m range cap)
  if (duration > 0) {
    float distanceCm = duration * 0.0343 / 2.0;
    Serial.print("DIST:");
    Serial.println(distanceCm, 1);
  }

  delay(80); // ~12 readings/sec — plenty for dwell/walkaway timing
}
