from flask import Flask,request, render_template, redirect
import sqlite3
import json
import os
import stripe
import secrets
import yagmail
from twilio.rest import Client
import smtplib, ssl

from dotenv import load_dotenv

load_dotenv()

account_sid = os.environ.get('account_sid')
auth_token = os.environ.get('auth_token')
msgsid = os.environ.get('msgsid')
stripeAPI = os.environ.get('stripeAPI')
emailpassword = os.environ.get('emailpassword')


context = ssl.create_default_context()



client = Client(account_sid, auth_token)

stripe.api_key = stripeAPI
app = Flask(__name__)
con = sqlite3.connect('dev.db', check_same_thread=False)

con.execute('''
CREATE TABLE IF NOT EXISTS appointment_types
    (type_id INTEGER PRIMARY KEY,
    length INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    price INTEGER NOT NULL
);
''')

con.execute('''
CREATE TABLE IF NOT EXISTS appointments
    (appointment_id INTEGER PRIMARY KEY,
    date TEXT,
    time TEXT,
    avaliable BOOLEAN NOT NULL,
    appointment_type INTEGER,
    FOREIGN KEY (appointment_type)
        REFERENCES appointment_types (type_id)
             ON DELETE NO ACTION 
             ON UPDATE NO ACTION
);
''')

con.execute('''
CREATE TABLE IF NOT EXISTS bookings
    (booking_id INTEGER PRIMARY KEY,
    booking_uuid TEXT NOT NULL,
    payed BOOLEAN NOT NULL,
    altered BOOLEAN NOT NULL DEFAULT 0,
    name text NOT NULL,
    email text NOT NULL,
    phone text NOT NULL,
    notes text,
    appointment_id INTEGER,
    FOREIGN KEY (appointment_id) 
      REFERENCES appointments (appointment_id) 
         ON DELETE CASCADE 
         ON UPDATE NO ACTION
);
''')



@app.route('/')
def index():
    return 'p'


@app.route('/cancel')
def cancel():
    """
    #TODO write cancel HTML page
    :return:
    """
    return 'Why did you cancel?'

@app.route('/success')
def success():
    """
    #TODO write success HTML page
    :return:
    """
    return 'WHoop Whoop you paid'

@app.route('/availability',methods=["POST"])
def availability_api():
    data = request.get_json()
    date = data.get('date', '')
    avaliable = list(con.execute(f"""
    SELECT appointment_id,time
    FROM appointments
    WHERE avaliable==true AND date=={date};"""))
    return json.dumps(avaliable)

@app.route('/book/<type>/<date>')
def booking(type,date):
    avaliable = list(con.execute(f"""
        SELECT appointment_id,time,appointment_type
        FROM appointments
        WHERE avaliable==true AND date=='{date}'
        ORDER BY time ASC;"""))

    details = list(con.execute(f"""
                SELECT title,description,price
                FROM appointment_types
                WHERE type_id=={type};"""))

    return render_template('booking.html',avaliable=avaliable,title=details[0][0],desc=details[0][1],price=details[0][2])

@app.route('/stripe-payment', methods=['POST'])
def stripe_payment():
    data = request.form
    time = data.get('time', '')
    appointment_type = data.get('type', '')

    name = data.get('name', '')
    email = data.get('email', '')
    notes = data.get('notes', '')
    phone = data.get('phone', '')

    details = list(con.execute(f"""
            SELECT title,description,price
            FROM appointment_types
            WHERE type_id=={appointment_type};"""))

    booking_uuid = secrets.token_urlsafe(16)
    check = list(con.execute(f"""
                    SELECT *
                    FROM bookings
                    WHERE booking_uuid=="{booking_uuid}";"""))
    while check:
        booking_uuid = secrets.token_urlsafe(16)
        check = list(con.execute(f"""
                            SELECT *
                            FROM bookings
                            WHERE booking_uuid=="{booking_uuid}";"""))

    con.execute(f"""
    INSERT INTO bookings (booking_uuid,payed,name,email,phone,notes,appointment_id) VALUES ('{booking_uuid}',{0},'{name}','{email}','{phone}','{notes}','{appointment_type}')
    """)
    con.commit()
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        customer_email=email,
        line_items=[{
          'price_data': {
            'currency': 'gbp',
            'product_data': {
                'name': f"{details[0][0]} ({time})",
                'description': f"{details[0][1]}"
            },
            'unit_amount': details[0][2],
          },
          'quantity': 1,
        }],
        mode='payment',
        success_url=f'http://127.0.0.1:5000/success/{booking_uuid}',
        cancel_url='http://127.0.0.1:5000/cancel',
    )

    return redirect(session.url, code=303)

@app.route('/success/<code>')
def confirm_booking(code):
    con.execute(f"""
        UPDATE bookings 
        SET payed=1
        WHERE booking_uuid == '{code}';
        """)
    con.commit()
    id = list(con.execute(f"""
            SELECT appointment_id
            FROM bookings
            WHERE bookings.booking_uuid == '{code}';
            """))[0][0]

    con.execute(f"""
        UPDATE appointments
        SET avaliable=0
        WHERE appointment_id == '{id}';
    """)
    con.commit()

    name,email,phone,appointment_id = list(con.execute(f"""
                                SELECT name,email,phone,appointment_id
                                FROM bookings
                                WHERE booking_uuid=="{code}";"""))[0]

    time,date = list(con.execute(f"""
                                SELECT time,date
                                FROM appointments
                                WHERE appointment_id=="{appointment_id}";"""))[0]


    message = client.messages.create(
        messaging_service_sid=msgsid,
        body=f'Hello, {name}. This message is to confirm your booking at {time} on the {date}.',
        to=phone
    )
    message = client.messages.create(
        messaging_service_sid='MG3f0b06cfc3627932c09a1fd1d3f674c3',
        body=f'{name} booked. This message is to confirm they booked a session at {time} on the {date}.',
        to='+447444431413'
    )
    receiver = "johnmontgomery2003@gmail.com"



    yag = yagmail.SMTP("test134832418524@gmail.com", password=emailpassword)
    yag.send(
        to=receiver,
        subject="PT Session Booking",
        contents=f'{name} booked. This message is to confirm they booked a session at {time} on the {date}.'
    )
    return 'hello!'

if __name__ == '__main__':
    app.run()
