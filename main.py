######################################################
#
#      Autor: Armin Scheu
#      Created: 2023
#      Description: Welp, its Kahoot!, but way shittier
#
#
######################################################

######################
# install needed modules:
# pip install Flask flask-socketio

from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import join_room, leave_room, send, SocketIO
from string import ascii_uppercase
import random
import json
import re

app = Flask(__name__)
app.config["SECRET_KEY"] = "QlBh9jGwUBhwcjjbUkiSNVk2LxEJE5iAErGfqKyOQY2H2rmNYEVLelSN9gMFQgbni3NKdTzV5xtCu4hE3OPpuehrVyyvLRvBczkZAqBbqSnSKtOPOHvLkLDrk8HxmzbY"
socketio = SocketIO(app)

rooms = {}
adminrooms = {}
dashboard = {}

################### Functions

# Generates a random uppercase roomcode
def generate_unique_code(length):
    while True:
        code = ""

        for _ in range(length):
            code  += random.choice(ascii_uppercase)

        if code not in rooms:
            break
    
    return code

# Changes the current question
def changeCurrentQuestion(data, skipquestion):
    adminroom = session.get("adminroom")
    room = getRoomFromAdminRoom(adminroom)
    currIndex = getCurrIndexByRoom(room)

    if data != False:
        if currIndex is None:
            socketio.emit("error", "Keine Fragen eingetragen", to=adminroom)
            return

        moreCurrIndex = currIndex + skipquestion

        if moreCurrIndex >= 0 and moreCurrIndex < len(jsonLoadsQuestions(room)):
            rooms[room]["currentquestion"] += skipquestion
            print("Room " + room + " chaneged to question " + str(moreCurrIndex))
            updateQuestions(adminroom)

# Sends updated questions to all admin and user rooms
def updateQuestions(adminroom):
    room = getRoomFromAdminRoom(adminroom)
    questionobj = getCurrentQuestions(room)
    dashboardcode = getDashboardCodeFromRoomCode(room)

    currIndex = getCurrIndexByRoom(room)
    questionobj[currIndex]["currentquestion"] = currIndex
    content = questionobj[currIndex]

    socketio.emit("updateQuestions", content, to=room)
    socketio.emit("updateQuestions", {"content": content, "toggle": True}, to=dashboardcode)
    #socketio.emit("updateQuestions", {"testing" : "testing"}, to=adminroom) !!!!! THIS IS BROKEN, PLS FIX !!!!!

def jsonLoadsQuestions(room):
    return json.loads("\"" + str(getCurrentQuestions(room)) + "\"")

def getDashboardCodeFromRoomCode(room):
    keys = [i for i in dashboard.keys()]
    values = [i for i in dashboard.values()]
    
    return keys[values.index(room)]

# Gets the current question from a room
def getCurrentQuestions(room):

    if room not in rooms:
        return

    question = rooms[room]["questions"]
            
    return json.loads(str(question))

def getCurrentQuestion(room):
    currIndex = getCurrIndexByRoom(room)
    questions = getCurrentQuestions(room)

    return questions[currIndex]

def getCurrIndexByRoom(room):
    return rooms[room]["currentquestion"]

# Gets the room code from adminroomcode
def getRoomFromAdminRoom(adminroom):
    return adminrooms[adminroom]

def getAndSortUserByScore(room, limit):
    users = rooms[room]["members"]

    # do some sick sortin' right here
    
    tempusers = []
    for name, score in users.items(): 
        tempusers.append({"name": name, "score": score["score"] })

    if limit > 0:
        tempusers = tempusers[:limit]

    return tempusers


#################### Routs

@app.route("/admin")
def admin():
    adminroom = session.get("adminroom")

    if adminroom is None or adminroom not in adminrooms:
        return redirect(url_for("home"))
    
    room = adminrooms[adminroom]
    dashboardcode = getDashboardCodeFromRoomCode(room)

    return render_template("admin.html", admincode=adminroom, usercode=room, dashboardcode=dashboardcode, questions=getCurrentQuestions(room), currentquestion=getCurrIndexByRoom(room), users=getAndSortUserByScore(room, -1))

@app.route("/quiz", methods=["POST", "GET"])
def quiz():
    room = session.get("room")
    name = session.get("name")

    if room not in rooms:
       return redirect(url_for("home"))
    
    currentroom = rooms[room]

    currIndex = currentroom["currentquestion"]

    if currIndex is None:
        return render_template("home.html", error = "Room is not ready to start", code=room, name=name)

    thisQuestion = getCurrentQuestion(room)

    hasUserAlreadyAnswered = name in thisQuestion["solvedBy"]

    return render_template("quiz.html", question=thisQuestion, alreadySolved=hasUserAlreadyAnswered)

@app.route("/", methods=["POST", "GET"])
def home():
    sessiontoken = session.get("sessiontoken")
    session.clear()

    roomcode = request.args.get("code")
    
    isRoomCode = (roomcode is not None)

    if roomcode is None:
        roomcode = ""

    if request.method == "POST":
        name = request.form.get("name")
        room = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)

        if not name and create == False:
            return render_template("home.html", error = "Please enter a name.", code=room, name=name, disableCreateNew = isRoomCode)
        
        if join != False and not room:
            return render_template("home.html", error = "Please enter a room code.", code=room, name=name, disableCreateNew = isRoomCode)
        
        if create != False:
            room = generate_unique_code(4)
            adminroom = generate_unique_code(24)
            dashboardcode = generate_unique_code(16)
            
            rooms[room] = {
                "members": {},
                "currentquestion": None,
                "questions": []
                }
            
            adminrooms[adminroom] = room
            dashboard[dashboardcode] = room

            session["adminroom"] = adminroom
            return redirect(url_for("admin"))
        elif room not in rooms:
            return render_template("home.html", error = "Invalid code", code=room, name=name, disableCreateNew = isRoomCode)
        
        if name == "admin" and room in adminrooms:
            session["adminroom"] = room
            return redirect(url_for("admin"))
        
        if name in rooms[room]["members"]:
            if sessiontoken != rooms[room]["members"][name]["sessiontoken"]:
                return render_template("home.html", error = "Username already taken", code=room, name=name, disableCreateNew = isRoomCode)
        else:
            session["sessiontoken"] = generate_unique_code(32)

        session["name"] = name
        session["room"] = room

        return redirect(url_for("quiz"))

    return render_template("home.html", code=roomcode, disableCreateNew = isRoomCode)

@app.route("/results")
def results():
    dashboardcode = request.args.get("dashboard")

    if dashboardcode is None or dashboardcode not in dashboard:
        return redirect(url_for("home"))

    room = dashboard[dashboardcode]
    session["room"] = room

    tempusers = getAndSortUserByScore(room, 4)

    return render_template("results.html", roomcode=room, question=getCurrentQuestion(room), users=tempusers)


################### Admin Controlls

@socketio.on("previous")
def previous(data):
    changeCurrentQuestion(data, -1)

@socketio.on("next")
def next(data):
    changeCurrentQuestion(data, 1)

@socketio.on("commit")
def adminChange(data):
    adminroom = session.get("adminroom")
    room = getRoomFromAdminRoom(adminroom)

    questions = re.sub('\s+', ' ', data["data"]["questions"])

    rooms[room]["questions"] = questions
    
    if getCurrIndexByRoom(room) is None:
        rooms[room]["currentquestion"] = 0

    updateQuestions(adminroom)

@socketio.on("userKick")
def userKick(name):
    room = session.get("room")
    
    if room in rooms:
        del rooms[room]["members"][name]
         
@socketio.on("results")
def results(data):
    adminroom = session.get("adminroom")
    room = getRoomFromAdminRoom(adminroom)

    dashboardcode = getDashboardCodeFromRoomCode(room)

    socketio.emit("leaderboard", {"user": getAndSortUserByScore(room, 4), "toggle": False}, to=dashboardcode)



################### User Actions

@socketio.on("answer")
def answer(data):
    room = session.get("room")
    name = session.get("name")
    adminroom = session.get("adminroom")

    
    question = getCurrentQuestion(room)


    if room is None or name is None:
        return
    
    if room not in rooms:
        leave_room(room)
        return
    
    if data["buttonPressed"]:

        count =  data["buttonPressed"]  
        socketio.emit("countQuestion",{"count": count}, to=dashboardcode)

    if data["buttonPressed"] == question["correct"]:

        timeRemaining = question["time"] - data["timedifference"]
        percentage = timeRemaining / question["time"]
        points = round(percentage * 1000)

        question["solvedBy"].append(name)
        
        rooms[room]["members"][name]["score"] += points
        
        socketio.emit("changeScore", {"name": name, "score": rooms[room]["members"][name]["score"]}, to=adminroom)   


################### Other Handlers

@socketio.on("connect")
def connect(auth):
    room = session.get("room")
    name = session.get("name")
    adminroom = session.get("adminroom")
    dashboardcode = request.args.get("dashboard")

    if room is None or name is None:
        return
    
    if room not in rooms:
        leave_room(room)
        return
    
    if adminroom is not None:
        join_room(adminroom)
    elif  dashboardcode is not None:
        join_room(dashboardcode)
    else:
        join_room(room)
        socketio.emit("userJoin", {"name": name, "score": 0}, to=adminroom)

        rooms[room]["members"][name] = {"sessiontoken": session.get("sessiontoken"), "score": 0}

        print(f"{name} joined room {room}")

@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    adminroom = session.get("adminroom")
    name = session.get("name")
    dashboardcode = request.args.get("dashboard")

    if adminroom is None:
        leave_room(room)
        if room in rooms:
            del rooms[room]["members"][name]
            socketio.emit("userLeve", {"name": name}, to=adminroom)
    elif dashboardcode is None:
        leave_room(dashboardcode)
    else:
        leave_room(adminroom)

    send({"name": name, "message": "has left the room"}, to=room)
    print(f"{name} has left room {room}")


########### Main

if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5001)