from flask import Blueprint, render_template, request, redirect, url_for

from db import conn, cursor

auth = Blueprint("auth", __name__)


@auth.route("/")
def home():
    return render_template("login.html")


@auth.route("/register", methods=["POST"])
def register():

    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")

    cursor.execute(
        """
        INSERT INTO users (name, email, password)
        VALUES (%s, %s, %s)
        """,
        (name, email, password)
    )

    conn.commit()

    return "Registration Successful, Please Log in again."


@auth.route("/login", methods=["POST"])
def login():

    email = request.form.get("email")
    password = request.form.get("password")

    cursor.execute(
        """
        SELECT * FROM users
        WHERE email = %s
        AND password = %s
        """,
        (email, password)
    )

    user = cursor.fetchone()

    if user:
        return "dashboard"

    return "Invalid email or password"