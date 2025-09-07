from pymavlink import mavutil

# Connect to the PX4 autopilot (adjust the connection string as needed)
# For serial: connection_string = '/dev/ttyUSB0', baud=57600
# For UDP: connection_string = 'udp:127.0.0.1:14550'
connection_string = "udp:127.0.0.1:14551"
master = mavutil.mavlink_connection(connection_string)

print("Waiting for heartbeat...")
master.wait_heartbeat()
print("Heartbeat received!")

while True:
    msg = master.recv_match(type=["GLOBAL_POSITION_INT", "ATTITUDE"], blocking=True)
    if not msg:
        continue

    if msg.get_type() == "GLOBAL_POSITION_INT":
        lat = msg.lat / 1e7
        lon = msg.lon / 1e7
        alt = msg.alt / 1000.0  # in meters
        print(f"Position: lat={lat:.7f}, lon={lon:.7f}, alt={alt:.2f}m")
    elif msg.get_type() == "ATTITUDE":
        roll = msg.roll
        pitch = msg.pitch
        yaw = msg.yaw
        print(f"Attitude: roll={roll:.3f}, pitch={pitch:.3f}, yaw={yaw:.3f}")
