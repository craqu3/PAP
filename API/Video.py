import cv2 as cv

cam = cv.VideoCapture(1)



try:
    while True:
        returning, frame = cam.read()
        cv.imshow('Original Image', frame)
        if cv.waitKey(1) == ord('esc'):
            break
except not returning:
    print("Error")
except not cam:
    print("No cam found")


cv.imshow('Original Image', frame)



cam.release()
cv.destroyAllWindows()