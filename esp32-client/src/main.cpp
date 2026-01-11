#include <Arduino.h>
#include <WiFi.h>

#define LED_PIN 15
#define LED_RED 40
#define LED_YELLOW 38
#define LED_GREEN 36

// Seznam WiFi sítí (nahraďte názvy a hesla svými hodnotami)
struct WifiCred {
  const char* ssid;
  const char* pass;
};

WifiCred wifiCreds[] = {
  { "YOUR_SSID_1", "YOUR_PASSWORD_1" },
  { "YOUR_SSID_2", "YOUR_PASSWORD_2" },
  // Přidejte další sítě podle potřeby
};
const size_t WIFI_CREDS_COUNT = sizeof(wifiCreds) / sizeof(wifiCreds[0]);

unsigned long loopCount = 0; // počítadlo průchodů loop()

// Blink timing (milliseconds). Halved to make LEDs blink 2× faster.
#define BLINK_DELAY 500

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

  // Připojení k WiFi (zkusíme více sítí, jednu po druhé)
  WiFi.mode(WIFI_STA);

  const unsigned long perNetworkTimeout = 8000; // ms na jednu síť
  bool connected = false;
  for (size_t i = 0; i < WIFI_CREDS_COUNT; ++i) {
    const char* trySsid = wifiCreds[i].ssid;
    const char* tryPass = wifiCreds[i].pass;

    Serial.print("Zkousim WiFi '");
    Serial.print(trySsid);
    Serial.print("'...");

    WiFi.begin(trySsid, tryPass);

    unsigned long startAttempt = millis();
    while (WiFi.status() != WL_CONNECTED && (millis() - startAttempt) < perNetworkTimeout) {
      delay(500);
      Serial.print('.');
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
      Serial.print("WiFi pripojeno ('");
      Serial.print(trySsid);
      Serial.print("'), IP: ");
      Serial.println(WiFi.localIP());
      connected = true;
      break;
    } else {
      Serial.print("Nepodarilo se pripojit k '");
      Serial.print(trySsid);
      Serial.println("' - pokracuje dal...");
    }
  }

  if (!connected) {
    Serial.println("Nebyla nalezena zadna dostupna WiFi (vsechny pokusy selhaly).");
  }
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
  delay(BLINK_DELAY);

  digitalWrite(LED_PIN, LOW);
  digitalWrite(LED_RED, LOW);
  digitalWrite(LED_YELLOW, LOW);
  digitalWrite(LED_GREEN, LOW); // LED vypnout
  delay(BLINK_DELAY);
}
