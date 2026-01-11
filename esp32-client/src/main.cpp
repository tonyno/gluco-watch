#include <Arduino.h>

#define LED_PIN 15
#define LED_RED 40
#define LED_YELLOW 38
#define LED_GREEN 36

unsigned long loopCount = 0; // počítadlo průchodů loop()

void setup()
{
  pinMode(LED_PIN, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  pinMode(LED_YELLOW, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);

  Serial.begin(115200); // inicializace sériové linky
  // while (!Serial) {            // počká na otevření Serial Monitoru (u ESP32 není nutné, ale nevadí)
  //   delay(10);
  // }

  Serial.println("ESP32 startuje...");
}

void loop()
{
  loopCount++;
  Serial.print("Pocet pruchodu loop(): ");
  Serial.println(loopCount);

  digitalWrite(LED_PIN, HIGH);
  digitalWrite(LED_RED, HIGH);
  digitalWrite(LED_YELLOW, HIGH);
  digitalWrite(LED_GREEN, HIGH); // LED zapnout
  delay(1000);

  digitalWrite(LED_PIN, LOW);
  digitalWrite(LED_RED, LOW);
  digitalWrite(LED_YELLOW, LOW);
  digitalWrite(LED_GREEN, LOW); // LED vypnout
  delay(1000);
}
