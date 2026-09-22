"""
VigiDrive - AI Driver Monitoring System
Main entry point
"""

import cv2
import time
import argparse
import serial

from core.detector import DriverMonitor
from core.alert import AlertSystem
from utils.display import Dashboard


def parse_args():
    parser = argparse.ArgumentParser(
        description="VigiDrive - AI Driver Monitoring System"
    )

    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="Camera index (default: 0)"
    )

    parser.add_argument(
        "--no-display",
        action="store_true",
        help="Run without display (headless)"
    )

    parser.add_argument(
        "--arduino-port",
        default="COM3",
        help="Arduino serial port"
)

    parser.add_argument(
        "--save-log",
        action="store_true",
        help="Save event log to file"
    )

    parser.add_argument(
        "--sensitivity",
        type=str,
        default="medium",
        choices=["low", "medium", "high"],
        help="Detection sensitivity (default: medium)"
    )

    return parser.parse_args()


def main():

    args = parse_args()

    print("=" * 50)
    print("   VigiDrive - AI Driver Monitoring System")
    print("=" * 50)

    print(f"[INFO] Camera Index : {args.camera}")
    print(f"[INFO] Sensitivity  : {args.sensitivity}")
    print(f"[INFO] Save Log     : {args.save_log}")

    print("[INFO] Initializing system...")

    # -------------------------------------------------
    # Initialize VigiDrive components
    # -------------------------------------------------

    monitor = DriverMonitor(
        sensitivity=args.sensitivity
    )

    alert_sys = AlertSystem(
        save_log=args.save_log
    )

    dashboard = Dashboard()

    # -------------------------------------------------
    # Arduino connection
    # -------------------------------------------------

    arduino = None

    if args.arduino_port:

        try:

            arduino = serial.Serial(
                args.arduino_port,
                9600,
                timeout=1
            )

            time.sleep(2)

            print(
                f"[INFO] Arduino connected on "
                f"{args.arduino_port}."
            )

        except serial.SerialException as exc:

            print(
                f"[WARN] Arduino unavailable: {exc}"
            )

            print(
                "[WARN] Continuing without Arduino."
            )

            arduino = None

    # -------------------------------------------------
    # Camera
    # -------------------------------------------------

    cap = cv2.VideoCapture(args.camera)

    if not cap.isOpened():

        print(
            "[ERROR] Cannot open camera. "
            "Check camera index."
        )

        if arduino:
            arduino.close()

        return

    cap.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        1280
    )

    cap.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        720
    )

    cap.set(
        cv2.CAP_PROP_FPS,
        30
    )

    print(
        "[INFO] System ready. Press 'q' to quit.\n"
    )

    # -------------------------------------------------
    # FPS
    # -------------------------------------------------

    fps_time = time.time()
    frame_count = 0

    # -------------------------------------------------
    # Eye-closure tracking
    #
    # This is specifically for the BUZZER.
    # It does NOT use result.drowsy.
    # -------------------------------------------------

    eyes_closed_frames = 0

    # Number of consecutive frames required
    # before the buzzer turns ON.
    EYES_CLOSED_CONSEC_FRAMES = 10

    # Use the EAR threshold from detector configuration
    EAR_THRESHOLD = monitor.cfg["EAR_THRESHOLD"]

    print(
        f"[INFO] EAR threshold: {EAR_THRESHOLD}"
    )

    print(
        f"[INFO] Eye closure frames: "
        f"{EYES_CLOSED_CONSEC_FRAMES}"
    )

    # -------------------------------------------------
    # Main loop
    # -------------------------------------------------

    try:

        while True:

            ret, frame = cap.read()

            if not ret:

                print(
                    "[ERROR] Failed to grab frame."
                )

                break

            frame_count += 1

            # -------------------------------------------------
            # Core analysis
            # -------------------------------------------------

            result = monitor.analyze(frame)

            # -------------------------------------------------
            # BUZZER CONTROL
            #
            # IMPORTANT:
            # Do NOT use result.drowsy here.
            #
            # Buzzer is controlled ONLY by EAR.
            # -------------------------------------------------

            if result.ear < EAR_THRESHOLD:

                eyes_closed_frames += 1

            else:

                # Eyes opened -> immediately reset
                eyes_closed_frames = 0

            # -------------------------------------------------
            # Send command to Arduino
            # -------------------------------------------------

            if arduino is not None:

                if eyes_closed_frames >= EYES_CLOSED_CONSEC_FRAMES:

                    # Eyes continuously closed
                    arduino.write(b'D')

                else:

                    # Eyes open / normal
                    arduino.write(b'A')

            # -------------------------------------------------
            # Normal VigiDrive alerts
            # -------------------------------------------------

            alert_sys.process(result)

            # -------------------------------------------------
            # Display
            # -------------------------------------------------

            if not args.no_display:

                display_frame = dashboard.render(
                    frame,
                    result,
                    alert_sys.get_active_alerts()
                )

                # FPS calculation
                if frame_count % 30 == 0:

                    elapsed = time.time() - fps_time

                    if elapsed > 0:

                        fps = 30 / elapsed

                        dashboard.fps = fps

                    fps_time = time.time()

                cv2.imshow(
                    "VigiDrive Monitor",
                    display_frame
                )

                # Quit with Q
                if cv2.waitKey(1) & 0xFF == ord('q'):

                    print(
                        "\n[INFO] Shutting down VigiDrive..."
                    )

                    break

    finally:

        # -------------------------------------------------
        # Make sure buzzer is OFF before shutdown
        # -------------------------------------------------

        if arduino is not None:

            try:

                arduino.write(b'A')
                time.sleep(0.1)
                arduino.close()

                print(
                    "[INFO] Arduino disconnected."
                )

            except Exception:
                pass

        cap.release()

        cv2.destroyAllWindows()

        alert_sys.close()

        print(
            "[INFO] Session ended."
        )


if __name__ == "__main__":
    main()