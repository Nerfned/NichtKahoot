# pip install Flask
# pip install flask-socketio

from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import join_room, leave_room, send, SocketIO
import random
from string import ascii_uppercase

app = Flask(__name__)
app.config["SECRET_KEY"] = "048133dd-9e31-493e-a968-b750d81f5848"
socketio = SocketIO(app)

rooms = {}
adminrooms = {}

def generate_unique_code(length):
    while True:
        code = ""

        for _ in range(length):
            code  += random.choice(ascii_uppercase)

        if code not in rooms:
            break
    
    return code



@app.route("/admin", methods=["POST", "GET"])
def admin():
    adminroom = session.get("adminroom")

    if adminroom is None or adminroom not in adminrooms:
        return redirect(url_for("home"))
    
    if request.method == "POST":
        questions = session.get("questions")
        commit = session.get("commit", False)
        kick = session.get("kick", False)
        previous = session.get("questions", False)
        result = session.get("questions", False)
        next = session.get("questions", False)

        if next != False:
            rooms[adminrooms[adminroom]]["currentquestion"] += 1

            send({
                "currentquestion": currentquestion
                }, to=room)

        pass

    roomcode = adminrooms[adminroom]
    questions = rooms[roomcode]["questions"]

    currentquestion = rooms[roomcode]["currentquestion"]

    users = rooms[roomcode]["members"]

    return render_template("admin.html", admincode=adminroom, usercode=roomcode, questions=questions, currentquestion=currentquestion, users=users)

@app.route("/quiz", methods=["POST", "GET"])
def quiz():
    if request.method == "POST":
        name = request.form.get("name")
        roomcode = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)

    return render_template("quiz.html", question=rooms[roomcode])

@app.route("/", methods=["POST", "GET"])
def home():
    session.clear()
    if request.method == "POST":
        name = request.form.get("name")
        code = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)

        if not name:
            return render_template("home.html", error = "Pease enter a name.", code=code, name=name)
        
        if join != False and not code:
            return render_template("home.html", error = "Pease enter a room code.", code=code, name=name)
        
        room = code
        if create != False:
            room = generate_unique_code(4)
            adminroom = generate_unique_code(16)
            
            rooms[room] = {
                "members": [],
                "currentquestion": 0,
                "questions": []
                }
            adminrooms[adminroom] = room
            
            session["adminroom"] = adminroom
            return redirect(url_for("admin"))
        elif code not in rooms:
            return render_template("home.html", error = "Invalid code", code=code, name=name)
        
        if name == "admin" and len(room) == 16:
            session["adminroom"] = adminroom
            return redirect(url_for("admin"))
        
        session["name"] = name
        session["sessiontoken"] = generate_unique_code(32)
        session["room"] = room

        return redirect(url_for("quiz"))

    return render_template("home.html")

@app.route("/room")
def room():
    room = session.get("room")

    if room is None or session.get("name") is None or room not in rooms:
        return redirect(url_for("home"))

    return render_template("room.html", code=room, messages=rooms[room]["messages"])

@socketio.on("message")
def message(data):
    room = session.get("room")
    
    if room not in rooms:
        return
    
    name = session.get("name")
    ddata = data["data"]

    content = {
        "name": name,
        "message": ddata
    }

    send(content, to=room)
    rooms[room]["messages"].append(content)
    print(f"{name} said: {ddata}")

@socketio.on("connect")
def connect(auth):
    room = session.get("room")
    name = session.get("name")
    
    if room is None or name is None:
        return
    
    if room not in rooms:
        leave_room(room)
        return
    
    join_room(room)
    send({"name": name, "message": "has entered the room"}, to=room)
    rooms[room]["members"] += 1
    print(f"{name} joined room {room}")

@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    name = session.get("name")

    leave_room(room)

    if room in rooms:
        rooms[room]["members"] -= 1
        if rooms[room]["members"] <= 0:
            del rooms[room]
            print(f"deleted room {room}")

    send({"name": name, "message": "has left the room"}, to=room)
    print(f"{name} has left room {room}")

if __name__ == "__main__":
    socketio.run(app, debug=True)