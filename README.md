AI-Powered Facial Recognition Access Control System

A smart access control system that recognises faces in real time, logs every entry, and alerts on unauthorised access. Built with Python Flask, OpenCV, Firebase, and an ESP32 microcontroller, with a web dashboard for live monitoring and user management.

What it does

The system replaces a key or card with your face. A camera feed runs through face recognition, and when someone approaches the door the system decides whether they are a known user. Recognised users get access and the event is logged. Unknown faces trigger an email alert so whoever manages the space knows straight away.
It reached 95% recognition accuracy under controlled lighting.

Features

-Real time face detection and recognition from a live camera feed.

-Automated door control through an ESP32 driving a solenoid lock.

-Web dashboard with live video monitoring.

-Role based user management, so you can add or remove people and set who has access.

-Email alerts when an unauthorised face is detected.

-Access event logging stored in Firebase.

How it fits together
__________________________________________________________
|Layer	            | Technology                          |
___________________________________________________________
|Face recognition   |	Python, OpenCV                      |
___________________________________________________________
|Backend and API    |	Flask                               |
___________________________________________________________
|Database and auth	| Firebase Realtime Database          |
___________________________________________________________
|Hardware control	  | ESP32 microcontroller, solenoid lock|
___________________________________________________________
|Interface	        | Responsive web dashboard            |
___________________________________________________________

The Flask backend runs the recognition logic and talks to Firebase, which stores users and access logs. When access is granted the backend signals the ESP32, which releases the lock. The dashboard reads from the same Firebase data so monitoring stays live. The electronics sit in a custom PVC enclosure built to make the system deployment ready rather than a loose breadboard prototype.

Repository contents
```
facial-recognition-access-control/
├── README.md
├── docs/
│   └── Facial_Recognition_Documentation.pdf
├── backend/
│   ├── app.py                 # Flask server and recognition logic
│   └── requirements.txt
├── esp32/
│   └── lock_control.ino       # Microcontroller firmware
├── dashboard/                 # Web interface
└── screenshots/
```
Setup
```bash
git clone https://github.com/naksMann/facial-recognition-access-control.git
cd facial-recognition-access-control/backend
pip install -r requirements.txt
python app.py
```
You will need to add your own Firebase configuration and flash the ESP32 with the firmware in the `esp32/` folder.

Tools used
Python, OpenCV, Flask, Firebase, ESP32, HTML/CSS/JavaScript

Demo
Project live demonstration: https://youtu.be/OAYKzZmYNtQ

Author
Nakedi Tumelo Peta (naksMann)
Computer Systems Engineering, Tshwane University of Technology
