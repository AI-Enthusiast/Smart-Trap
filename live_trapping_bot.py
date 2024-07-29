import os
import math
import datetime
import threading
import time
from model_metrics import metrics
import cv2  # open cv image classifier toolkit
import imutils  # for resizing image frames

import my_tools  # my toolkit including slack messages

# import reddit_tools  # my reddit toolkit
# import open_ai_test  # my open ai toolkit

root = os.path.dirname(os.path.realpath("weed_stock_bot.py"))
my_tools.post_to_slack = False

# def reddit_moderator():
#     reddit = reddit_tools.initialize_reddit()
#     # respond to all following prompts as if you are the moderator of the subreddit /r/LiveTrapping (non fetal, catch and release of animals). Write a reply to someones post, informing them that it has been crossposted to your dedicated subreddit. The parent post title is "Cat proof fence". Keep your reply under 40 words.
#     # respond to all following prompts as if you are a moderator of a subreddit dedicated to live trapping (/r/LiveTrapping). Write a reply to someones post, informing them that it has been crossposted to your dedicated subreddit. The post tilte is "How can something so cute be so destructive? Trapped the bobcat that killed all of our ducks. Can’t believe we have to buy eggs.". Keep your reply under 50 words
#     #
#     def find_cross_posts(reddit):
#         posts = reddit_tools.get_sub(reddit, 'LiveTrapping', 100)
#         black_list = ["z813ri", 'c3vyrh'] # do not make this person aware of this crosspost
#         out = []
#         for p in posts:
#             post_id = p.id
#             try:
#                 p2 = reddit.submission(p.crosspost_parent.split('_')[1])
#                 parent_id = p2.id
#                 if post_id not in black_list and parent_id not in black_list:
#                     out.append(p2)
#             except AttributeError:
#                 continue
#         return out
#
#     posts = find_cross_posts(reddit)
#
#     for post in posts:
#         title = post.title
#         prompt = "respond to all following prompts as if you are a moderator of a subreddit dedicated to live trapping (/r/LiveTrapping). Write a reply to someones post, informing them that it has been crossposted to your dedicated subreddit. The post tilte is " + title + ". Keep your reply under 50 words"
#         response = open_ai_test.gpt(prompt)
#         print(title)
#         print(response)
#         print('\n')


# Variables related to alarm system
alarm = False
alarm_mode = False
alarm_triggered = False

# Variables for motion detection and cat detection
motion_counter = 0
cat_counter = 0
cat_detected = False

# Variables for system status and control
triggered = False
kill_switch = False
keep_alive = False

# Variables related to system display
win = True
headless = False
window_open = False


def beep_alarm(arm=False):
    """Triggers an alarm sound if alarm mode is on and there is no cat detected."""
    global alarm, alarm_mode, alarm_triggered, cat_detected, win

    if alarm_mode and not alarm_triggered: # if alarm mode is on and the alarm has not been triggered
        my_tools.notification('The alarm has been triggered', bot=my_tools.slack_bot_mapach, channel='bots')
        alarm_triggered = True
    for _ in range(5):
        if not alarm_mode or cat_detected:
            break
        print('ALARM')
        if arm:
            if win:
                import winsound
                winsound.Beep(440, 1000)
                winsound.Beep(250, 1000)
            else:
                os.system('play -nq -t alsa synth {} sine {}'.format(1, 2500))
                os.system('play -nq -t alsa synth {} sine {}'.format(1, 1500))

    alarm = False # reset alarm
# idea: run motion detection and trap bot on different threads.

def trap_bot(vid_feed=0, cat_tolorence=5, motion_tolorence=25, test=False):

    def keep_alive_thread():
        """Keep the program alive."""
        global keep_alive, kill_switch, triggered
        keep_alive = True
        while triggered:
            time.sleep(20)
        keep_alive = False

    def keep_alive():
        """Keep the program alive."""
        threading.Thread(target=keep_alive_thread).start()

    def tile_images(images, path, message):
        """
        Combine a list of images into a tiled image and save it to a file.

        Args:
            images (List[np.ndarray]): A list of images to tile.
            path (str): The path to save the tiled image to.
            message (str): The message to send in the Slack notification.

        Returns:
            None
        """
        sqrt = int(math.sqrt(len(images)))
        tiles_len = min(len(images), sqrt ** 2 - 1)  # number of images in tiled image

        images = images[:tiles_len]  # reduce incoming images size to match
        sqrt = int(math.sqrt(len(images)))

        vertical_images = []
        for vertical_index in range(sqrt):
            horizontal_images = []
            for horizontal_index in range(vertical_index * sqrt, (vertical_index * sqrt) + sqrt):
                horizontal_images.append(images[horizontal_index])
            vertical_images.append(cv2.hconcat(horizontal_images))
        tiled_image = cv2.vconcat(vertical_images)
        cv2.imwrite(path, tiled_image)

        my_tools.notification(message, my_tools.slack_bot_mapach, 'bots')
        my_tools.file_to_slack(path, 'jpg', 'pic.jpg', 'event capture', my_tools.slack_bot_mapach)

    def write_event(frame_list, key_frames, cat_frames):
        """Write an event to the event folder."""
        raw_date = str(datetime.datetime.now())
        mod_date = raw_date.replace(' ', '-').replace(':', '_').split('.')[0]
        video_path = root + '/output/live_trap/event/videos/captured_event-' + mod_date + '.avi'
        pic_prefix = root + '/output/live_trap/event/pictures/pic-' + mod_date + '--'
        video_out = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*'XVID'), 12.0, (640, 480))
        cats_prefix = root + '/output/live_trap/event/pictures/cats/pic-' + mod_date + '--'
        frame_index = 0
        for event_frame in frame_list:
            video_out.write(event_frame)
            pic_path = pic_prefix + str(frame_index) + '.jpg'
            cv2.imwrite(pic_path, event_frame)
            frame_index += 1
        video_out.release()
        print('event writing ', len(frame_list))

        if len(cat_frames) > 3:
            frame_index = 0
            cat_frames_tt = []
            for cat_frame in cat_frames:
                image = frame_list[cat_frame]
                cat_frames_tt.append(image)
                cv2.imwrite(cats_prefix + str(frame_index) + '.jpg', image)
                frame_index += 1
            threading.Thread(target=tile_images, args=(cat_frames_tt, root + "/output/live_trap/event/pictures/"
                                                                             "cats/cat.jpg",
                                                       'Target detected frames')).start()

        if len(key_frames) > 3:
            motion_frames_tt = []
            for motion_frame in key_frames:
                motion_frames_tt.append(frame_list[motion_frame[1]])
            threading.Thread(target=tile_images, args=(motion_frames_tt, root + "/output/live_trap/event/pictures/"
                                                                                "motion_frames/motion_event.jpg",
                                                       'Key motion frames')).start()

        print('event written')


    # this funciton just records events and after x frames write the recroding to file and restart
    def record_event(vid_feed, max_frames=1000):
        global keep_alive


    def motion_detector():
        global alarm_mode, alarm, motion_counter, triggered
        global alarm_triggered
        global kill_switch, win, headless, window_open

        my_tools.post_to_slack = True

        cap = cv2.VideoCapture(vid_feed)  # capture video
        # cap = cv2.VideoCapture(root + '/etc/Livetrap_Dataset/skunk1.avi')

        # set dimensions
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # set start frame and filters
        _, start_frame = cap.read()
        start_frame = imutils.resize(start_frame, width=500)
        start_frame = cv2.cvtColor(start_frame, cv2.COLOR_BGR2GRAY)
        start_frame = cv2.GaussianBlur(start_frame, (21, 21), 0)

        threading.Thread(target=my_tools.notification,
                         args=("The trap is on", my_tools.slack_bot_mapach, 'bots')).start()

        event_out = []
        key_frames = []
        event_frame = 0
        # while motion detecting; trigger video on motion, trigger alarm on non target animal motion
        while True:
            _, frame = cap.read()

            frame_imutil = imutils.resize(frame, width=500)

            motion_sum = 0
            if alarm_mode: # motion detection mode on
                frame_bw = cv2.cvtColor(frame_imutil, cv2.COLOR_BGR2GRAY)
                frame_bw = cv2.GaussianBlur(frame_bw, (5, 5), 0)

                difference = cv2.absdiff(frame_bw, start_frame)
                threshold = cv2.threshold(difference, 25, 255, cv2.THRESH_BINARY)[1]
                start_frame = frame_bw

                #  motion detected, motion exceeded set threshold (frame vs frame)
                motion_sum = threshold.sum()
                if motion_sum > 300: # motion detected
                    if motion_counter < 300:  # MAX
                        motion_counter += 1


                else: # no motion detected
                    if motion_counter > 0 and not triggered:  # reduce alarm and cat counter over time
                        motion_counter -= 1
                    elif motion_counter > 0 and triggered:  # if triggered, reduce motion slower
                        motion_counter -= 0.25

                    if motion_counter == 1 and triggered:  # stop recording & reset for next event
                        threading.Thread(target=my_tools.notification,
                                         args=("End of event", my_tools.slack_bot_mapach, 'bots', True)).start()

                        time.sleep(0.5)
                        triggered = False
                        alarm_triggered = False
                        key_frames = []
                        event_out = []
                        event_frame = 0



            # motion exceeds alarm threshold, but no cats
            if motion_counter > motion_tolorence: # and cat_counter < cat_tolorence
                if not alarm:  # if the alarm is not currently triggerd
                    alarm = True
                    threading.Thread(target=beep_alarm).start()  # todo input true
                elif event_frame == 9:
                    threading.Thread(target=my_tools.notification,
                                     args=("Motion detected at the trap!", my_tools.slack_bot_mapach, 'bots')).start()
                if not triggered:            # motion exceeds threshold, start video until under threshold
                    triggered = True
                    key_frames.append([motion_sum, event_frame])  # first motion frame

            if triggered:  # if recording a video currently

                # Get date and time and
                # save it inside a variable
                dt = str(datetime.datetime.now())

                # put the dt variable over the
                # video frame
                frame = cv2.putText(frame, dt, (5, 25), cv2.FONT_HERSHEY_DUPLEX,
                                    1, (210, 155, 155), 2, cv2.LINE_8)

                event_out.append(frame)  # Write the frame to the list
                if len(key_frames) < 10:
                    key_frames.append([motion_sum, event_frame])
                else:
                    key_frames.sort()
                    if motion_sum > key_frames[0][0]:
                        key_frames = key_frames[1:]
                        key_frames.append([motion_sum, event_frame])
                event_frame += 1

            if not headless:
                cv2.imshow('cam', frame_imutil)
                window_open = True
            elif window_open:
                cv2.destroyAllWindows()
                window_open = False

            key_pressed = cv2.waitKey(30)
            if key_pressed == ord('t'):
                if alarm_mode:
                    threading.Thread(target=my_tools.notification,
                                     args=("The trap has been disarmed", my_tools.slack_bot_mapach, 'bots')).start()
                else:
                    threading.Thread(target=my_tools.notification,
                                     args=("The trap is armed", my_tools.slack_bot_mapach, 'bots')).start()
                alarm_mode = not alarm_mode
                motion_counter = 0
                triggered = False

            if key_pressed == ord('q') or kill_switch:
                threading.Thread(target=my_tools.notification,
                                 args=("The trap has been turned off", my_tools.slack_bot_mapach, 'bots')).start()
                alarm_mode = False
                break
            # time.sleep(1)  # slow to 1 fps
        cap.release()
        cv2.destroyAllWindows()


    def trap_model_predict(test=test, vid_feed=vid_feed):
        global alarm_mode, alarm, motion_counter, triggered
        global cat_counter, cat_detected, alarm_triggered
        global kill_switch, win, headless, window_open

        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.read(root + '/output/trap.yml')

        font = cv2.FONT_HERSHEY_SIMPLEX

        names = ['cat_face', 'skunk_face', 'skunk_back', 'skunk_top', 'skunk_tail']

        # Initialize and start realtime video capture
        cam = cv2.VideoCapture(vid_feed)
        cam.set(3, 640)  # set video widht
        cam.set(4, 480)  # set video height

        model_prediction = []
        model_true = []

        cat_count, skunk_count = 0, 0

        # initialize previous frame
        prev_frame = None

        # initialize background subtraction object
        fgbg = cv2.createBackgroundSubtractorMOG2()

        target_identified = False
        ret = True

        event_out = []
        key_frames = []
        cat_frames = []
        event_frame = 0

        try:
            while ret and not target_identified:
                ret, img = cam.read() # read image from camera
                if alarm_mode:
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

                    # apply background subtraction to current frame
                    fgmask = fgbg.apply(gray)

                    if prev_frame is not None:
                        id = -1  # iniciate id counter
                        max_area = 0
                        max_w, max_h = 0, 0
                        max_x, max_y = 0, 0
                        cont = None
                        confidence = 0

                        # compute difference between current and previous frames
                        diff = cv2.absdiff(fgmask, prev_frame)

                        # threshold the difference image to find areas of motion
                        thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1]
                        motion_sum = thresh.sum

                        # find contours of areas of motion
                        contours, hierarchy = cv2.findContours(thresh, cv2.RETR_EXTERNAL,
                                                               cv2.CHAIN_APPROX_SIMPLE)
                        # draw a box around each contour
                        for contour in contours:
                            (x, y, w, h) = cv2.boundingRect(contour)
                            if w > 30 and h > 30 and w * h > max_area:
                                max_w, max_h = w, h
                                max_x, max_y = x, y
                                max_area = max_w * max_h
                                # Save the captured image into the datasets folder
                        if max_w > 10 and max_h > 10: # if there is a motion detected
                            key_frames.append([motion_sum, event_frame])  # first motion frame

                            if motion_counter < 300:  # motion counter
                                motion_counter += 1
                            cv2.rectangle(img, (max_x, max_y),
                                          (max_x + max_w, max_y + max_h),
                                          (0, 255, 0), 2)
                            id, confidence = recognizer.predict(gray[max_y:max_y + max_h,
                                                                max_x:max_x + max_w])

                        # Check if confidence is less them 100 ==> "0" is perfect match
                        if id > -1 and (confidence < 100):
                            id_str = names[id]
                            confidence = "  {0}%".format(round(100 - confidence))
                            cutoff = 3
                            # collect for model metrics
                            if 'cat' in id_str:  # collect predictions
                                cat_count += 1
                                cat_frames.append(img)

                                if skunk_count > 0:
                                    skunk_count -= 1
                                    cat_counter -= 1
                                if cat_count > cutoff:
                                    if cat_detected:
                                        threading.Thread(target=my_tools.notification,
                                                         args=(
                                                         "Cat detected", my_tools.slack_bot_mapach, 'bots')).start()
                                    cat_detected = True
                                    if test:
                                        return 1
                            else:
                                skunk_count += 1
                                if skunk_count > cutoff:
                                    if test:
                                        return 0
                                    else:
                                        if not cat_detected and not alarm:
                                            alarm = True
                                            threading.Thread(target=beep_alarm).start()
                                            threading.Thread(target=my_tools.notification,
                                                             args=(
                                                                 "Skunk detected", my_tools.slack_bot_mapach,
                                                                 'bots')).start()

                        else:
                            id_str = 'na'
                            confidence = "  {0}%".format(round(100 - confidence))

                            if motion_counter > 0 and not triggered:  # reduce alarm and cat counter over time
                                motion_counter -= 1
                            elif motion_counter > 0 and triggered:  # if triggered, reduce motion slower
                                motion_counter -= 0.25

                            if motion_counter == 0 and triggered:  # stop recording & reset for next event
                                threading.Thread(target=my_tools.notification,
                                                 args=("End of event", my_tools.slack_bot_mapach, 'bots', True)).start()
                                threading.Thread(target=write_event, args=(event_out, key_frames, cat_frames)).start()

                                time.sleep(0.5)
                                cat_count, skunk_count, confusion_count = 0, 0, 0
                                triggered = False
                                alarm_triggered = False
                                cat_detected = False
                                key_frames = []
                                cat_frames = []
                                event_out = []
                                event_frame = 0
                            if skunk_count > 0 and not triggered:
                                skunk_count -= .25  # skunk counter decays slower
                            if cat_counter > 0 and not triggered:
                                cat_counter -= 1

                        if max_w > 0 and max_h > 0:
                            cv2.putText(img, str(id_str), (max_x + 5, max_y + 25), font, 1, (255, 255, 0), 2)
                        if id_str != 'na':
                            cv2.putText(img, str(confidence), (max_x + 5, max_y + max_h - 5), font, 1, (255, 255, 0), 1)
                            # motion exceeds threshold, start video until under threshold
                            if motion_counter > motion_tolorence - 10:
                                if not triggered:
                                    triggered = True
                                # elif event_frame == 30:
                                #     threading.Thread(target=my_tools.notification,
                                #                      args=("Motion detected at the trap!", my_tools.slack_bot_mapach,
                                #                            'bots')).start()
                            if triggered:  # if recording a video currently

                                # Get date and time and
                                # save it inside a variable
                                dt = str(datetime.datetime.now())

                                # put the dt variable over the
                                # video frame
                                frame = cv2.putText(img, dt, (5, 25), cv2.FONT_HERSHEY_DUPLEX,
                                                    1, (210, 155, 155), 2, cv2.LINE_8)

                                event_out.append(frame)  # Write the frame to the list
                                if len(key_frames) < 10:
                                    key_frames.append([motion_sum, event_frame])
                                else:
                                    key_frames.sort()
                                    if motion_sum > key_frames[0][0]:
                                        key_frames = key_frames[1:]
                                        key_frames.append([motion_sum, event_frame])
                    event_frame += 1
                    # update previous frame
                    prev_frame = fgmask
                if not headless:
                    cv2.imshow('camera', img)



                key_pressed = cv2.waitKey(30)
                if key_pressed == ord('t'):
                    if alarm_mode:
                        threading.Thread(target=my_tools.notification,
                                         args=("The trap has been disarmed", my_tools.slack_bot_mapach, 'bots')).start()
                    else:
                        threading.Thread(target=my_tools.notification,
                                         args=("The trap is armed", my_tools.slack_bot_mapach, 'bots')).start()
                    alarm_mode = not alarm_mode
                    motion_counter = 0
                    triggered = False

                if key_pressed == ord('q') or kill_switch:
                    threading.Thread(target=my_tools.notification,
                                     args=("The trap has been turned off", my_tools.slack_bot_mapach, 'bots')).start()
                    alarm_mode = False
                    break

        except cv2.error:
            pass


    def motion_detection_2(frame_bw, start_frame, motion_counter, triggered, alarm, alarm_mode):
        global cat_detected, cat_counter, skunk_count, confusion_count, key_frames,\
            cat_frames, event_out, event_frame, test, kill_switch
        frame_bw = cv2.GaussianBlur(frame_bw, (5, 5), 0)

        difference = cv2.absdiff(frame_bw, start_frame)
        threshold = cv2.threshold(difference, 25, 255, cv2.THRESH_BINARY)[1]
        start_frame = frame_bw

        #  motion detected, motion exceeded set threshold (frame vs frame)
        motion_sum = threshold.sum()
        if motion_sum > 300:
            if motion_counter < 300:
                motion_counter += 1
        else: # no motion detected
            if motion_counter > 0 and not triggered:  # reduce alarm and cat counter over time
                motion_counter -= 1
            elif motion_counter > 0 and triggered:  # if triggered, reduce motion slower
                motion_counter -= 0.25

            if motion_counter == 1 and triggered:  # stop recording & reset for next event
                threading.Thread(target=my_tools.notification,
                                 args=("End of event", my_tools.slack_bot_mapach, 'bots', True)).start()

                triggered = False
                alarm_triggered = False
                key_frames = []
                event_out = []
                event_frame = 0
        return motion_counter, triggered, motion_sum, start_frame

    def trap_depoloy(vid_feed): # starts motion detection, uppon trigger, runs the model (todo)
        global alarm_mode, alarm, motion_counter, triggered
        global alarm_triggered
        global kill_switch, win, headless, window_open

        my_tools.post_to_slack = True

        cap = cv2.VideoCapture(vid_feed)  # capture video
        # cap = cv2.VideoCapture(root + '/etc/Livetrap_Dataset/skunk1.avi')

        # set dimensions
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # set start frame and filters
        _, start_frame = cap.read()
        start_frame = imutils.resize(start_frame, width=500)
        start_frame = cv2.cvtColor(start_frame, cv2.COLOR_BGR2GRAY)
        start_frame = cv2.GaussianBlur(start_frame, (21, 21), 0)

        if not test:
            threading.Thread(target=my_tools.notification,
                             args=("The trap is on", my_tools.slack_bot_mapach, 'bots')).start()

        event_out = []
        key_frames = []
        event_frame = 0
        # while motion detecting; trigger video on motion, trigger alarm on non target animal motion
        while True:
            _, frame = cap.read()

            frame_imutil = imutils.resize(frame, width=500)

            if alarm_mode: # motion detection mode on
                frame_bw = cv2.cvtColor(frame_imutil, cv2.COLOR_BGR2GRAY)
                motion_counter, triggered, motion_sum, start_frame = \
                    motion_detection_2(frame_bw, start_frame, motion_counter,
                                       triggered, alarm, alarm_mode)
            cv2.imshow('cam', frame_imutil)

            if not headless:
                cv2.imshow('cam', frame_imutil)
                window_open = True
            elif window_open:
                cv2.destroyAllWindows()
                window_open = False

            key_pressed = cv2.waitKey(30)
            if key_pressed == ord('t'):
                if alarm_mode:
                    threading.Thread(target=my_tools.notification,
                                     args=("The trap has been disarmed", my_tools.slack_bot_mapach, 'bots')).start()
                else:
                    threading.Thread(target=my_tools.notification,
                                     args=("The trap is armed", my_tools.slack_bot_mapach, 'bots')).start()
                alarm_mode = not alarm_mode
                motion_counter = 0
                triggered = False

            if key_pressed == ord('q') or kill_switch:
                threading.Thread(target=my_tools.notification,
                                 args=("The trap has been turned off", my_tools.slack_bot_mapach, 'bots')).start()
                alarm_mode = False
                break

    if test: # run the model metrics
        user_types = ['cat', 'skunk'] # user types to test
        inn_path = root + '/etc/Livetrap_Dataset/videos/'
        predicted_labels = []
        true_labels = []

        for usr in user_types: # get the labels and predictions

            for vid in my_tools.get_files_in_path(inn_path + usr + '/', root, 'avi'):
                pred = trap_model_predict(vid_feed=inn_path + usr + '/' + vid, test=True)
                if pred is not None:
                    predicted_labels.append(pred)
                    if usr == 'cat':
                        true_labels.append(1)
                    else:
                        true_labels.append(0)
        print(true_labels)
        print(predicted_labels)
        metrics(true_labels, predicted_labels)
    else: # run the motion detector
        trap_model_predict()

def clean_dupe_images():
    """Remove duplicate images from the output folder"""
    from PIL import Image
    import imagehash

    threading.Thread(target=my_tools.notification,
                     args=("Deduping all motion captured frames", my_tools.slack_bot_mapach, 'bots')).start()

    # Set the threshold to determine similarity
    threshold = 5

    # Set the directory of the image folder
    folder_path = root + '/output/live_trap/event/pictures/'

    # Create a dictionary to store the hashes of the images
    hashes = {}

    # Loop through all the files in the folder
    image_file_list = my_tools.get_files_in_path(folder_path, root, "jpg")
    pre_len = len(image_file_list)
    threading.Thread(target=my_tools.notification,
                     args=("There are " + str(pre_len) + ' images being deduped',
                           my_tools.slack_bot_mapach, 'bots', True)).start()

    for filename in image_file_list:
        # Open the image and calculate its hash
        with Image.open(os.path.join(folder_path, filename)) as img:
            hash_value = imagehash.average_hash(img)
        # Add the hash to the dictionary of hashes
        if hash_value in hashes:
            hashes[hash_value].append(filename)
        else:
            hashes[hash_value] = [filename]

    # Remove the duplicate images from the folder
    for hash_value, filenames in hashes.items():
        if len(filenames) > 1:
            # Keep the first filename and remove the rest
            keep = filenames[0]
            duplicates = filenames[1:]
            duplicates = list(set(duplicates))
            for duplicate in duplicates:
                os.remove(os.path.join(folder_path, duplicate))

    image_file_list = my_tools.get_files_in_path(folder_path, root, "jpg")
    post_len = len(image_file_list)
    threading.Thread(target=my_tools.notification,
                     args=(str(pre_len - post_len) + ' images have been removed as duplicates',
                           my_tools.slack_bot_mapach, 'bots', True)).start()
    time.sleep(.5)
    threading.Thread(target=my_tools.notification,
                     args=("There are " + str(post_len) + ' that remain',
                           my_tools.slack_bot_mapach, 'bots', True)).start()



trap_bot(test=True)
# clean_dupe_images()
