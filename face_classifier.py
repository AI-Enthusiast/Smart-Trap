import os

import cv2

root = os.path.dirname(os.path.realpath("face_classifier.py"))

# Load the pre-trained cascade classifier for detecting faces
face_cascade = cv2.CascadeClassifier(root + "\etc\Faces_Dataset\haarcascade_frontalface_default.xml")

# Start the video capture
cap = cv2.VideoCapture(0)
while True:
    # Read a frame from the video capture
    ret, frame = cap.read()

    # Convert the frame to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Detect faces in the grayscale frame
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)

    # Draw rectangles around the detected faces
    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

    # Display the processed frame
    cv2.imshow("Face Recognition", frame)

    # Check if the user pressed the "q" key to quit
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

# Release the video capture and destroy the window
cap.release()
cv2.destroyAllWindows()