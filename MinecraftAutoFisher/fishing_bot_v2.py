import cv2
import numpy as np
import win32api
import win32con
import mss
import time
import os
import random

# --- CONFIGURATION ---
TEMPLATE_PATH = 'bobber.png'
TOGGLE_KEY = 0x46             # 'F' key
CONFIDENCE_THRESHOLD = 0.50   
SINK_THRESHOLD = 6            
SETTLE_TIME = 1.5             
LOST_TIMEOUT = 10.0           
ROI_SIZE = 300                
GONE_FRAME_LIMIT = 5          

def win_right_click():
    win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
    time.sleep(random.uniform(0.05, 0.1))
    win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)

def get_red_mask(img_bgr):
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    lower_red1 = np.array([0, 70, 50])
    upper_red1 = np.array([15, 255, 255])
    lower_red2 = np.array([160, 70, 50])
    upper_red2 = np.array([180, 255, 255])
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    return cv2.bitwise_or(mask1, mask2)

def catch_and_recast():
    print("\n[!] BITE DETECTED! Reeling in...")
    win_right_click()
    time.sleep(random.uniform(1.0, 1.5))
    print("[+] Recasting...")
    win_right_click()
    time.sleep(0.5)

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    if not os.path.exists(TEMPLATE_PATH):
        print(f"ERROR: '{TEMPLATE_PATH}' not found!")
        return

    tpl_bgr = cv2.imread(TEMPLATE_PATH)
    tpl_mask = get_red_mask(tpl_bgr)
    th, tw = tpl_mask.shape[:2]
    
    print("\n" + "="*40)
    print("      MINECRAFT PRO FISHING BOT V3.1")
    print("="*40)
    print(" > Press 'F' to START the bot")
    print(" > Press 'F' again to STOP/PAUSE")
    print("="*40)

    bot_active = False
    key_was_down = False
    
    base_y = None
    lock_pos = None 
    last_seen = time.time()
    fish_caught = 0
    gone_frames = 0
    
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        
        while True:
            # --- TOGGLE LOGIC ---
            key_state = win32api.GetAsyncKeyState(TOGGLE_KEY)
            if key_state & 0x8000: # Key is currently pressed
                if not key_was_down:
                    bot_active = not bot_active
                    key_was_down = True
                    if bot_active:
                        print("\n>>> BOT STARTED! Fishing now...")
                        # Reset tracking state on start
                        base_y, lock_pos, gone_frames = None, None, 0
                        last_seen = time.time()
                    else:
                        print("\n>>> BOT STOPPED / PAUSED.")
                    time.sleep(0.2) # Debounce
            else:
                key_was_down = False

            if not bot_active:
                time.sleep(0.1) # Idle low CPU
                continue

            # --- BOT LOGIC ---
            screenshot = sct.grab(monitor)
            img_bgr = np.array(screenshot)[:,:,:3]
            
            ox, oy = 0, 0
            if lock_pos:
                lx, ly = lock_pos
                x1, y1 = max(0, int(lx - ROI_SIZE//2)), max(0, int(ly - ROI_SIZE//2))
                x2, y2 = min(img_bgr.shape[1], int(lx + ROI_SIZE//2)), min(img_bgr.shape[0], int(ly + ROI_SIZE//2))
                search_area = img_bgr[y1:y2, x1:x2]
                ox, oy = x1, y1
            else:
                search_area = img_bgr

            search_mask = get_red_mask(search_area)
            res = cv2.matchTemplate(search_mask, tpl_mask, cv2.TM_CCOEFF_NORMED)
            _, val, _, loc = cv2.minMaxLoc(res)
            
            curr_x, curr_y = loc[0] + ox, loc[1] + oy

            if val >= CONFIDENCE_THRESHOLD:
                last_seen = time.time()
                gone_frames = 0
                
                if base_y is None:
                    print(f"--> Bobber found (Conf: {val:.2f}). Settling...")
                    time.sleep(SETTLE_TIME)
                    screenshot = sct.grab(monitor)
                    fresh_bgr = np.array(screenshot)[:,:,:3]
                    fresh_mask = get_red_mask(fresh_bgr)
                    _, _, _, l_cal = cv2.minMaxLoc(cv2.matchTemplate(fresh_mask, tpl_mask, cv2.TM_CCOEFF_NORMED))
                    base_y = l_cal[1]
                    lock_pos = (l_cal[0] + tw//2, l_cal[1] + th//2)
                    print(f"--> LOCKED at Y={base_y}. Total: {fish_caught}")
                else:
                    diff_y = curr_y - base_y
                    if diff_y >= SINK_THRESHOLD:
                        fish_caught += 1
                        catch_and_recast()
                        base_y, lock_pos = None, None
                        time.sleep(2.0)
                    else:
                        lock_pos = (curr_x + tw//2, curr_y + th//2)
                        print(f"Tracking [Caught: {fish_caught}] | Conf: {val:.2f} | Y-Diff: {diff_y}    ", end='\r')
            else:
                if base_y is not None:
                    gone_frames += 1
                    if gone_frames >= GONE_FRAME_LIMIT:
                        fish_caught += 1
                        print(f"\n[!] BITE! (Disappeared)")
                        catch_and_recast()
                        base_y, lock_pos, gone_frames = None, None, 0
                        time.sleep(2.0)
                elif time.time() - last_seen > LOST_TIMEOUT:
                    print(f"\n[?] Bobber lost. Searching... [Total: {fish_caught}]")
                    base_y, lock_pos, gone_frames = None, None, 0
                    last_seen = time.time()

            time.sleep(0.02)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopping bot...")
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        input("Press Enter to close...")
