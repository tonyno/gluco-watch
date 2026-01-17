#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <TM1637Display.h>

#define LED_PIN 15
#define LED_RED 3
#define LED_YELLOW 7
#define LED_GREEN 5   

// Seznam WiFi sítí (nahraďte názvy a hesla svými hodnotami)
#include "secrets.h"

TM1637Display display(35, 33);

struct WifiCred {
  const char* ssid;
  const char* pass;
};

WifiCred wifiCreds[] = {
  { WIFI_SSID_1, WIFI_PASS_1 },
  { WIFI_SSID_2, WIFI_PASS_2 },
  // Přidejte další sítě podle potřeby (aktualizujte secrets.h a example)
};
const size_t WIFI_CREDS_COUNT = sizeof(wifiCreds) / sizeof(wifiCreds[0]);

unsigned long loopCount = 0; // počítadlo průchodů loop()

// Fetch interval and URL
const char* GLUCOSE_URL = "https://gluco-watch-default-rtdb.europe-west1.firebasedatabase.app/users/78347/latest.json";
const unsigned long FETCH_INTERVAL_MS = 1UL * 60UL * 1000UL; // 10 minutes
unsigned long lastFetchMs = 0;
void fetchGlucose();

// Blink timing (milliseconds). Halved to make LEDs blink 2× faster.
#define BLINK_DELAY 500

// Helper: show glucose as clock HH:MM on the 4-digit display
// - example: 3 -> 3:00, 3.51 -> 3:51
void showGlucoseAsClock(float glucose) {
  if (isnan(glucose) || glucose < 0.0f) {
    // show 0:00 for invalid values
    display.showNumberDecEx(0, 0b01000000, false, 4, 0);
    return;
  }

  int hours = (int)floor(glucose);
  float frac = glucose - (float)hours;
  int minutes = (int)round(frac * 100.0f);
  if (minutes >= 100) { // carry if rounding pushed minutes to 100
    minutes = 0;
    hours += 1;
  }

  if (hours > 99) {
    // cannot display more than 2-digit hours on 4-digit display; show 9999 as overflow
    display.showNumberDec(9999, true, 4, 0);
    return;
  }

  int val = hours * 100 + minutes; // e.g., 3:51 -> 351
  // Use dot/colon bit (0b01000000) to render colon between 2nd and 3rd digits
  display.showNumberDecEx(val, 0b01000000, false, 4, 0);
}

// Update LEDs based on glucose value:
// - red if glucose < 3.9
// - yellow if glucose > 10
// - green otherwise
void updateLedForGlucose(float glucose) {
  Serial.print("Aktualizuji LEDy podle cukru: ");
  Serial.println(glucose);

  // show as HH:MM on 4-digit display
  showGlucoseAsClock(glucose);

  if (glucose < 3.9f) {
    digitalWrite(LED_RED, HIGH);
    digitalWrite(LED_YELLOW, LOW);
    digitalWrite(LED_GREEN, LOW);
    Serial.println("Rozsvitena cervena LED");
  } else if (glucose > 10.0f) {
    digitalWrite(LED_RED, LOW);
    digitalWrite(LED_YELLOW, HIGH);
    digitalWrite(LED_GREEN, LOW);
    Serial.println("Rozsvitena zluta LED");
  } else {
    digitalWrite(LED_RED, LOW);
    digitalWrite(LED_YELLOW, LOW);
    digitalWrite(LED_GREEN, HIGH);
    Serial.println("Rozsvitena zelena LED");
  }
}

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

  display.setBrightness(0x0f);

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
  } else {
    // initial fetch immediately after successful WiFi connection
    fetchGlucose();
    lastFetchMs = millis();
  }
}

// Note: keep WiFi credentials out of source control. Use src/secrets.h (not committed) or environment-specific config.

void fetchGlucose() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi neni pripojena, preskakuji stahovani");
    WiFi.reconnect();
    return;
  }

  WiFiClientSecure client;
  client.setInsecure(); // NOTE: for simplicity; consider using proper root cert in production
  HTTPClient http;
  Serial.print("Stahuji: ");
  Serial.println(GLUCOSE_URL);
  if (http.begin(client, GLUCOSE_URL)) {
    int httpCode = http.GET();
    if (httpCode == HTTP_CODE_OK) {
      String payload = http.getString();
      Serial.println("Prijaty payload:");
      Serial.println(payload);

      // Parse JSON using ArduinoJson
      DynamicJsonDocument doc(1024);
      DeserializationError err = deserializeJson(doc, payload);
      if (err) {
        Serial.print("JSON parse error: ");
        Serial.println(err.c_str());
      } else {
        if (doc.containsKey("main") && doc["main"].is<JsonObject>()) {
          JsonObject main = doc["main"].as<JsonObject>();
          if (main.containsKey("glucose")) {
            float glucose = main["glucose"].as<float>();
            Serial.print("Hladina cukru: ");
            Serial.println(glucose);
            updateLedForGlucose(glucose);
          } else {
            Serial.println("Pole 'glucose' nebylo nalezeno v objektu 'main'.");
          }
        } else if (doc.containsKey("glucose")) {
          // fallback: top-level glucose
          float glucose = doc["glucose"].as<float>();
          Serial.print("Hladina cukru: ");
          Serial.println(glucose);
          updateLedForGlucose(glucose);
        } else {
          Serial.println("Pole 'main' nebo 'glucose' nebylo nalezeno v JSONu.");
        }
      }
    } else {
      Serial.print("HTTP GET selhalo, kod: ");
      Serial.println(httpCode);
    }
    http.end();
  } else {
    Serial.println("HTTP begin selhalo");
  }
}

void loop()
{
  loopCount++;
  Serial.print("Pocet pruchodu loop(): ");
  Serial.println(loopCount);

  // If WiFi disconnected, try to reconnect (non-blocking)
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi neni pripojena, pokusim se znovu pripojit...");
    WiFi.reconnect();
  }

  unsigned long now = millis();
  if (now - lastFetchMs >= FETCH_INTERVAL_MS) {
    fetchGlucose();
    lastFetchMs = now;
  }

  // Idle a bit to reduce CPU usage
  delay(1000);
}
