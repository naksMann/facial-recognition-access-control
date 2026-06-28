#include <WiFi.h>
#include <WebServer.h>

// --- Network credentials ---
const char* ssid = "HONOR";        // <<<--- REPLACE WITH YOUR WIFI/HOTSPOT NAME
const char* password = "naksMann"; // <<<--- REPLACE WITH YOUR WIFI/HOTSPOT PASSWORD

// --- Pin Definitions (LEFT SIDE ONLY) ---
const int greenLedPin = 26; // GPIO Pin for Green LED (Access Granted)
const int redLedPin   = 25; // GPIO Pin for Red LED (Access Denied / Idle)
const int relayPin    = 27; // GPIO Pin for Relay Module IN pin

// --- Configuration ---
const int unlockDuration = 2000; // How long the relay stays HIGH (in milliseconds) - e.g., 2 seconds

// --- Web Server object on port 80 ---
WebServer server(80);

// --- Function Prototypes ---
void connectWiFi();
void handleAccessGranted();
void handleAccessDenied();
void handleNotFound();
void updateActuators(bool granted); // Combined function

// --- Setup ---
void setup() {
  Serial.begin(115200);
  Serial.println("\nStarting ESP32 Door Lock Controller (LEDs + Relay)...");

  pinMode(greenLedPin, OUTPUT);
  pinMode(redLedPin, OUTPUT);
  pinMode(relayPin, OUTPUT);

  // Initial state: Locked
  digitalWrite(relayPin, LOW); // Relay OFF
  updateActuators(false);      // Red LED ON, Green OFF

  connectWiFi();

  // Define server routes
  server.on("/access_granted", HTTP_GET, handleAccessGranted); // Endpoint for success
  server.on("/access_denied", HTTP_GET, handleAccessDenied);   // Endpoint for failure
  server.onNotFound(handleNotFound); // Handle invalid requests

  // Start the server
  server.begin();
  Serial.println("HTTP server started. Ready for commands.");
}

// --- Main Loop ---
void loop() {
  // Handle incoming client requests
  server.handleClient();
  delay(10); // Small delay
}

// --- Function Implementations ---

void connectWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  int attempt = 0;
  while (WiFi.status() != WL_CONNECTED && attempt < 20) { // Timeout
    delay(500);
    Serial.print(".");
    attempt++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP()); // <<<--- NOTE THIS IP ADDRESS!
  } else {
    Serial.println("\nWiFi connection FAILED!");
    // Indicate failure (blink red LED)
    while(true) {
        digitalWrite(redLedPin, HIGH); delay(500);
        digitalWrite(redLedPin, LOW); delay(500);
    }
  }
}

// --- Request Handlers ---

void handleAccessGranted() {
  Serial.println("Received /access_granted request.");
  updateActuators(true); // Turn Green ON, Red OFF, Pulse Relay
  server.send(200, "text/plain", "OK: Access Granted Sequence Triggered");
}

void handleAccessDenied() {
  Serial.println("Received /access_denied request.");
  updateActuators(false); // Turn Red ON, Green OFF, Ensure Relay OFF
  server.send(200, "text/plain", "OK: Access Denied State Set");
}

void handleNotFound() {
  server.send(404, "text/plain", "Not Found");
  Serial.print("Handled 404 for: ");
  Serial.println(server.uri());
}

// --- Actuator Control Function ---

void updateActuators(bool granted) {
  if (granted) {
    // --- Access Granted Sequence ---
    digitalWrite(greenLedPin, HIGH); // Green ON
    digitalWrite(redLedPin, LOW);    // Red OFF
    Serial.println("LED State: GRANTED (Green ON)");

    // Pulse the relay HIGH (activate) then LOW (deactivate)
    digitalWrite(relayPin, HIGH);    // Activate Relay (Unlock)
    Serial.println("Relay ON (Unlocking)");
    delay(unlockDuration);         // Keep unlocked for specified duration
    digitalWrite(relayPin, LOW);     // Deactivate Relay (Lock)
    Serial.println("Relay OFF (Locking)");

    // Keep Green LED on a little longer for visual feedback, then revert to locked state
    delay(1000); // Additional delay with Green ON
    digitalWrite(greenLedPin, LOW); // Green OFF
    digitalWrite(redLedPin, HIGH); // Red ON (Back to idle/locked)
    Serial.println("LED State: Back to DENIED/IDLE (Red ON)");

  } else {
    // --- Access Denied / Idle State ---
    digitalWrite(greenLedPin, LOW); // Green OFF
    digitalWrite(redLedPin, HIGH);  // Red ON
    digitalWrite(relayPin, LOW);    // Ensure Relay is OFF (Locked)
    Serial.println("LED State: DENIED/IDLE (Red ON), Relay OFF");
  }
}
