import os
import threading
import time
import datetime
import uuid

import cv2
import imutils

import reddit_tools
import open_ai_test
import motion_detection_bot
import my_tools
from picamera.array import PiRGBArray
from picamera import PiCamera

root = os.path.dirname(os.path.realpath("weed_stock_bot.py"))
def reddit_moderator():
    reddit = reddit_tools.initialize_reddit()
    # respond to all following prompts as if you are the moderator of the subreddit /r/LiveTrapping (non fetal, catch and release of animals). Write a reply to someones post, informing them that it has been crossposted to your dedicated subreddit. The parent post title is "Cat proof fence". Keep your reply under 40 words.
    # respond to all following prompts as if you are a moderator of a subreddit dedicated to live trapping (/r/LiveTrapping). Write a reply to someones post, informing them that it has been crossposted to your dedicated subreddit. The post tilte is "How can something so cute be so destructive? Trapped the bobcat that killed all of our ducks. Can’t believe we have to buy eggs.". Keep your reply under 50 words
    #
    def find_cross_posts(reddit):
        posts = reddit_tools.get_sub(reddit, 'LiveTrapping', 100)
        black_list = ["z813ri", 'c3vyrh'] # do not make this person aware of this crosspost
        out = []
        for p in posts:
            post_id = p.id
            try:
                p2 = reddit.submission(p.crosspost_parent.split('_')[1])
                parent_id = p2.id
                if post_id not in black_list and parent_id not in black_list:
                    out.append(p2)
            except AttributeError:
                continue
        return out

    posts = find_cross_posts(reddit)

    for post in posts:
        title = post.title
        prompt = "respond to all following prompts as if you are a moderator of a subreddit dedicated to live trapping (/r/LiveTrapping). Write a reply to someones post, informing them that it has been crossposted to your dedicated subreddit. The post tilte is " + title + ". Keep your reply under 50 words"
        response = open_ai_test.gpt(prompt)
        print(title)
        print(response)
        print('\n')

alarm = False
alarm_mode = False
alarm_triggered = False
motion_counter = 0
cat_counter = 0
cat_detected = False
triggered = False
current_event = 0

def trap_bot(cat_tolorence = 5, motion_tolorence = 20):

    # cat_faces_cascade = cv2.CascadeClassifier(root + '/etc/Cat_Dataset/haarcascade_frontalcatface.xml')
    cat_faces_cascade = cv2.CascadeClassifier(root + "/etc/Faces_Dataset/haarcascade_frontalface_default.xml")

    def beep_alarm():
        global alarm
        global alarm_mode
        global alarm_triggered
        if alarm_mode and not alarm_triggered:
            my_tools.notification('The alarm has been triggered', bot=my_tools.slack_bot_mapach, channel='bots')
            alarm_triggered = True
        for _ in range(5):
            if not alarm_mode or cat_detected:
                break
            print('ALARM')
            # os.system('play -nq -t alsa synth {} sine {}'.format(1, 2500))

        alarm = False

    def motion_detector():
        global alarm_mode
        global alarm
        global motion_counter
        global triggered
        global cat_counter
        global cat_detected
        global current_event

        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        current_out = cv2.VideoWriter(root + '/output/live_trap/event/videos/captured_event_0.avi', fourcc, 20.0, (640, 480))

        # initialize the camera and grab a reference to the raw camera capture
        camera = PiCamera()
        camera.resolution = (640, 480)
        camera.framerate = 32
        rawCapture = PiRGBArray(camera, size=(640, 480))

        # allow the camera to warmup
        time.sleep(0.1)

        # cap = cv2.VideoCapture(0)  # capture video
        # cap = cv2.VideoCapture(root + '/etc/Livetrap_Dataset/cat1.avi')

        # set dimensions
        # cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        # cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # set start frame and filters
        # _, start_frame = cap.read()
        stf_raw = PiRGBArray(camera)
        time.sleep(.5)
        camera.capture(stf_raw, format = "bgr")
        start_frame = stf_raw.array
        #start_frame = imutils.resize(start_frame, width=500)
        start_frame = cv2.cvtColor(start_frame, cv2.COLOR_BGR2GRAY)
        start_frame = cv2.GaussianBlur(start_frame, (21, 21), 0)

        # while motion detecting; trigger video on motion, trigger alarm on non target animal motion
        for frame in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
            frame = frame.array
            # _, frame = cap.read()
            #frame_imutil = imutils.resize(frame, width=500)
            if alarm_mode:
                frame_bw = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                frame_bw = cv2.GaussianBlur(frame_bw, (5, 5), 0)

                difference = cv2.absdiff(frame_bw, start_frame)
                threshold = cv2.threshold(difference, 25, 255, cv2.THRESH_BINARY)[1]
                start_frame = frame_bw

                #  motion detected, motion exceeded set threshold (frame vs frame)
                if threshold.sum() > 300:
                    motion_counter += 1
                    # Detect cat faces in the image
                    faces = cat_faces_cascade.detectMultiScale(frame, scaleFactor=1.1, minNeighbors=5)

                    # Check if any faces were detected
                    if len(faces) == 0:  # if there are faces in the frame
                        print("No cat faces detected, motion count: " + str(motion_counter))
                    else:
                        cat_counter += 1
                        print("Cat faces detected, motion count: " + str(motion_counter))

                    # Draw rectangles around the cat faces
                    for (x, y, w, h) in faces:
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

                else:
                    if motion_counter > 0: # reduce alarm and cat counter over time
                        motion_counter -= 1
                    if motion_counter == 0 and triggered: # stop recording
                        current_out.release()
                        triggered = False
                        alarm_triggered = False
                        cat_detected = False
                        path_preffix = root + '/output/live_trap/event/videos/captured_event_'+ str(current_event)
                        os.rename(r''+path_preffix + '.avi', r''+path_preffix + '-' + str(datetime.datetime.now())
                                  .replace(' ', '_').replace(':', ',') + '.avi')

                        current_event += 1
                        path = root + '/output/live_trap/event/videos/captured_event_'+ str(current_event)+ '.avi'
                        current_out = cv2.VideoWriter(path, fourcc, 20.0, (640, 480))
                    if cat_counter > 0:
                        cat_counter -= .25  # cat counter decays slower

            if triggered: # if recording a video currently
                current_out.write(frame)  # Write the frame to the recording file
                print('Recording '+str(current_event)+' ...')

            cv2.imshow('cam', frame)

            if cat_counter > cat_tolorence:
                cat_detected = True
            # motion exceeds alarm threshold, but no cats
            if motion_counter > motion_tolorence and cat_counter < cat_tolorence:
                if not alarm: # if the alarm is not currently triggerd
                    alarm = True
                    threading.Thread(target=beep_alarm).start()
            # motion exceeds threshold, start video until under threshold
            if motion_counter > motion_tolorence - 10:
                path = root + '/output/live_trap/event/pictures/pic_' + str(current_event) + '-'+ str(uuid.uuid1()) + '.jpg'
                cv2.imwrite(path, frame)
                if not triggered:
                    triggered = True
                    print("Motion detected at the trap!")
                    threading.Thread(target=my_tools.notification,args=("Motion detected at the trap!", my_tools.slack_bot_mapach, 'bots')).start()
                    threading.Thread(target= my_tools.file_to_slack, args=(path, 'jpg', 'pic.jpg', 'event capture', my_tools.slack_bot_mapach)).start()

            key_pressed = cv2.waitKey(30)
            rawCapture.truncate(0)
            if key_pressed == ord('t'):
                alarm_mode = not alarm_mode
                motion_counter = 0
                triggered = False

            if key_pressed == ord('q'):
                alarm_mode = False
                break
            # time.sleep(1)  # slow to 1 fps
        rawCapture.release()
        current_out.release()
        cv2.destroyAllWindows()

    # my_tools.file_to_slack(root + '/output/output.avi', 'avi',
    #                    'output.avi', 'test',bot= my_tools.slack_bot_c_3p0)

    motion_detector()





trap_bot()
