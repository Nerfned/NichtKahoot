######################################################
#
#      Autor: Armin Scheu
#      Created: 2023
#      Description: Welp, its Kahoot!, but way shittier
#
#
######################################################

# pip install Flask
# pip install flask-socketio

from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import join_room, leave_room, send, SocketIO
from string import ascii_uppercase
import random
import json
import re

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

#################### Routs

@app.route("/admin", methods=["POST", "GET"])
def admin():
    sendcontent = None

    adminroom = session.get("adminroom")

    if adminroom is None or adminroom not in adminrooms:
        return redirect(url_for("home"))
    
    room = adminrooms[adminroom]
    currentquestion = rooms[room]["currentquestion"]
    users = rooms[room]["members"]
    
    if request.method == "POST":
        questions = request.form.get("questions")
        commit = request.form.get("commit", False)
        kick = request.form.get("kick", False)
        previous = request.form.get("previous", False)
        result = request.form.get("results", False)
        next = request.form.get("next", False)

        updateQuestions = False

        questions = re.sub('\s+',' ',questions)

        if next != False:
            if currentquestion is None:
                return render_template("admin.html", admincode=adminroom, usercode=room, questions=questions, currentquestion=currentquestion, users=users, error="Keine Fragen eingetragen")
            
            if rooms[room]["currentquestion"] < len(rooms[room]["questions"]):
                rooms[room]["currentquestion"] += 1

            updateQuestions = True
            
        if previous != False:
            if currentquestion is None:
                return render_template("admin.html", admincode=adminroom, usercode=room, questions=questions, currentquestion=currentquestion, users=users, error="Keine Fragen eingetragen")
            
            if rooms[room]["currentquestion"] > 0:
                rooms[room]["currentquestion"] -= 1

            updateQuestions = True
            
        if commit != False:
            rooms[room]["questions"] = questions
            
            if rooms[room]["currentquestion"] is None:
                rooms[room]["currentquestion"] = 0

            updateQuestions = True

        if updateQuestions:
            question = rooms[room]["questions"]
            questionobj = json.loads(question)

            socketio.emit("updateQuestions", questionobj[rooms[room]["currentquestion"]], to=room)

    questions = rooms[room]["questions"]
  
    tempusers = []
    for name, score in users.items():
        tempusers.append({"name": name, "score": score["score"] })

    tempusers
    return render_template("admin.html", admincode=adminroom, usercode=room, questions=questions, currentquestion=currentquestion, users=tempusers)

@app.route("/quiz", methods=["POST", "GET"])
def quiz():
    roomcode = session.get("room")
    name = session.get("name")

    if roomcode not in rooms:
       return redirect(url_for("home"))
    
    currentroom = rooms[roomcode]

    currentquestion = currentroom["currentquestion"]

    if currentquestion is None:
        return render_template("home.html", error = "Room is not ready to start", code=roomcode, name=name)

    question = currentroom["questions"]
    questionobj = json.loads(question)

    return render_template("quiz.html", question=questionobj[currentquestion])

@app.route("/", methods=["POST", "GET"])
def home():
    sessiontoken = session.get("sessiontoken")
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
                "members": {},
                "currentquestion": None,
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
        
        if name in rooms[room]["members"]:
            if sessiontoken != rooms[room]["members"][name]["sessiontoken"]:
                return render_template("home.html", error = "Username already taken", code=code, name=name)
        else:
            session["sessiontoken"] = generate_unique_code(32)

        session["name"] = name
        session["room"] = room

        return redirect(url_for("quiz"))

    return render_template("home.html")


# @app.route("/room")
# def room():
#     room = session.get("room")

#     if room is None or session.get("name") is None or room not in rooms:
#         return redirect(url_for("home"))

#     return render_template("room.html", code=room, messages=rooms[room]["messages"])


############################################ Web Sockets

# @socketio.on("message")
# def message(data):
#     room = session.get("room")
    
#     if room not in rooms:
#         return
    
#     name = session.get("name")
#     ddata = data["data"]

#     content = {
#         "name": name,
#         "message": ddata
#     }

#     send(content, to=room)
#     rooms[room]["messages"].append(content)
#     print(f"{name} said: {ddata}")

@socketio.on("answer")
def connect(data):
    room = session.get("room")
    name = session.get("name")
    adminroom = session.get("adminroom")
    
    question = json.loads(rooms[room]["questions"])[rooms[room]["currentquestion"]]

    if room is None or name is None:
        return
    
    if room not in rooms:
        leave_room(room)
        return
    
    if data["buttonPressed"] == question["correct"]:

        # percentile = data["timedifference"] * 100 / question["time"]
        # value = 1000 / percentile

        timeTaken = round(question["time"]/1000 * (question["time"] - data["timedifference"]))
        
        rooms[room]["members"][name]["score"] += timeTaken
        
        socketio.emit("changeScore", {"name": name, "score": rooms[room]["members"][name]["score"]}, to=adminroom)   

@socketio.on("connect")
def connect(auth):
    room = session.get("room")
    name = session.get("name")
    adminroom = session.get("adminroom")
    
    if room is None or name is None:
        return
    
    if room not in rooms:
        leave_room(room)
        return
    
    if adminroom is not None:
        join_room(adminroom)
    else:
        join_room(room)
        socketio.emit("userJoin", {"name": name, "score": 0}, to=adminroom)

        rooms[room]["members"][name] = {"sessiontoken": session.get("sessiontoken"),"score": 0}

        print(f"{name} joined room {room}")

@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    adminroom = session.get("adminroom")
    name = session.get("name")

    if adminroom is None:
        leave_room(room)
        if room in rooms:
            del rooms[room]["members"][name]
            socketio.emit("userLeve", {"name": name}, to=adminroom)
    else:
        leave_room(adminroom)


    send({"name": name, "message": "has left the room"}, to=room)
    print(f"{name} has left room {room}")

########### Main

if __name__ == "__main__":
    socketio.run(app, debug=True)