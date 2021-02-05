from flask import Flask, request, jsonify
from flask_restful import Resource, Api
from sqlalchemy import create_engine
from flask_cors import CORS, cross_origin
import pandas as pd  # data processing, CSV file I/O (e.g. pd.read_csv)
import pickle
import os.path
import train_model

from flask_socketio import *

def importModel():
    print('[+] Loading model')
    classifier = pickle.load(open("classifier.model", 'rb'))
    count_vectorizer = pickle.load(open("vectors.weights", 'rb'))
    print('[+] Model loaded')

def startServer():
    db_connect = create_engine('sqlite:///fakenews.db')
    app = Flask(__name__, static_folder='build', static_url_path='/')
    app.config['SECRET_KEY'] = 'some super secret key!'
    socketio = SocketIO(app, logger=True, cors_allowed_origins="*")

    api = Api(app)
    
    def predict(test):
        # 1: unreliable
        # 0: reliable
        print(test)
        test['total'] = test[0] + test[1]
        example_counts = count_vectorizer.transform(test['total'].values)
        predictions = classifier.predict_proba(example_counts)
        print(predictions[0][1])
        return predictions[0][1]


    @app.route('/', methods=['GET'])
    def api():
        return app.send_static_file('index.html')


    @app.route('/tweets', methods=['GET', 'POST'])  # allow both GET and POST requests
    def tweets():
        conn = db_connect.connect()  # connect to database
        if request.method == 'POST':  # this block is only entered when the form is submitted
            req_data = request.get_json()
            author = req_data['author']
            text = req_data['text']
            print(request.form)

            query = conn.execute("select full_name, username from users WHERE id = ? ;", author)
            res = query.fetchall()
            print(res[0])
            author_name = res[0][0]
            username = res[0][1]
            tweet = [[author_name, text]]

            pr = predict(pd.DataFrame(tweet))
            query = conn.execute("insert INTO tweets(author, text, score) VALUES (?, ?, ?);", author, text, pr)
            new_id = query.lastrowid
            conn.execute("insert INTO user_votes(tweet_id, down_votes) VALUES (?, ?);", new_id, 0)

            socketio.emit('new_tweet', {'full_name': author_name,
                                        'text': text,
                                        'prediction': pr,
                                        'username': username,
                                        'down_votes': 0})

            return {'author': author_name, 'text': text, 'score': pr}

        else:
            user_id = request.args.get('user_id')
            query = conn.execute("SELECT DISTINCT tweets.id, "
                                "full_name, "
                                "text, "
                                "author, "
                                "tweets.score AS prediction, "
                                "username, "
                                "down_votes, "
                                "voted.score AS yourScoring "
                                "FROM tweets "
                                "INNER JOIN network ON network.user_2 = tweets.author "
                                "INNER JOIN users ON users.id = network.user_2 "
                                "INNER JOIN user_votes ON user_votes.tweet_id = tweets.id "
                                "LEFT JOIN voted ON (voted.user_id = network.user_1 AND voted.tweet_id = tweets.id) "
                                "WHERE network.user_1 = ? "
                                "OR tweets.author = ? "
                                "ORDER BY tweets.id DESC ;", user_id, user_id)

            result = {'tweets': [dict(zip(tuple(query.keys()), i)) for i in query.cursor]}
            return jsonify(result)


    @app.route('/login', methods=['GET', 'POST'])
    def login():
        conn = db_connect.connect()  # connect to database
        if request.method == 'POST':  # this block is only entered when the form is submitted
            req_data = request.get_json()
            print(req_data)
            username = req_data['username']
            password = req_data['password']
            query = conn.execute("select * from users WHERE username = ? AND password = ?;", username, password)
            res = query.fetchall()
            if len(res) > 0:
                return jsonify({'id': res[0][0], 'username': res[0][1], 'full_name': res[0][3]})
            else:
                return {'error': True, 'message': 'No account exists'}
        else:
            return {'error': True, 'message': 'Error'}


    @app.route('/sign_up', methods=['POST', 'GET'])
    def sign_up():
        conn = db_connect.connect()  # connect to database
        if request.method == 'POST':  # this block is only entered when the form is submitted
            req_data = request.get_json()
            print(req_data)
            username = req_data['username']
            password = req_data['password']
            full_name = req_data['full_name']
            query = conn.execute("select id from users WHERE username = ? ;", username)
            if len([dict(zip(tuple(query.keys()), i)) for i in query.cursor]) > 0:
                return {'error': True, 'message': 'Account already exists'}
            else:
                query = conn.execute("INSERT INTO users (username, password, full_name) VALUES (?, ?, ?);", username, password,
                            full_name)
                conn.execute("INSERT INTO network(user_1, user_2) VALUES (?, ?) ;", query.lastrowid, query.lastrowid)

                return {'message': 'Success'}
        else:
            return {'error': True, 'message': 'Error'}


    @app.route('/follow', methods=['POST'])
    def follow():
        conn = db_connect.connect()  # connect to database
        if request.method == 'POST':  # this block is only entered when the form is submitted
            req_data = request.get_json()
            print(req_data)
            user_1 = req_data['user_id']
            user_2 = req_data['follow_id']
            query = conn.execute("select * from network WHERE user_1 = ? AND user_2 = ?;", user_1, user_2)
            if len([dict(zip(tuple(query.keys()), i)) for i in query.cursor]) > 0:
                return {'error': True, 'message': 'You already follow user '}
            else:
                conn.execute("INSERT INTO network(user_1, user_2) VALUES (?, ?) ;", user_1, user_2)
                return {'message': 'Success'}
        else:
            return {'error': True, 'message': 'Error'}


    @app.route('/unfollow', methods=['POST'])
    def unfollow():
        conn = db_connect.connect()  # connect to database
        if request.method == 'POST':  # this block is only entered when the form is submitted
            req_data = request.get_json()
            print(req_data)
            user_1 = req_data['user_id']
            user_2 = req_data['follow_id']
            query = conn.execute("select * from network WHERE user_1 = ? AND user_2 = ?;", user_1, user_2)
            if len([dict(zip(tuple(query.keys()), i)) for i in query.cursor]) < 0:
                return {'error': True, 'message': 'You are not following user '}
            else:
                query = conn.execute("DELETE from network WHERE user_1 = ? AND user_2 = ?;", user_1, user_2)
                return {'message': 'You have unfollowed user '}
        else:
            return {'error': True, 'message': 'Error'}


    @app.route('/following', methods=['POST', 'GET'])
    def followers():
        conn = db_connect.connect()  # connect to database
        if request.method == 'POST':  # this block is only entered when the form is submitted
            req_data = request.get_json()
            print(req_data)
            user_id = req_data['user_id']
            query = conn.execute("select full_name, username, users.id from network "
                                "INNER JOIN users ON network.user_1 = users.id "
                                "WHERE user_1 = ?;", user_id)
            return {'data': [dict(zip(tuple(query.keys()), i)) for i in query.cursor]}

        else:
            user_id = request.args.get('user_id')
            query = conn.execute("select full_name, username, users.id from network "
                                "INNER JOIN users ON network.user_2 = users.id "
                                "WHERE user_1 = ?;", user_id)
            return {'data': [dict(zip(tuple(query.keys()), i)) for i in query.cursor]}


    @app.route('/users', methods=['POST', 'GET'])
    def users():
        conn = db_connect.connect()  # connect to database
        user_id = request.args.get('user_id')
        # GET users that you are not following
        query = conn.execute("SELECT id, username, full_name "
                            "FROM users WHERE id != ? "
                            "AND id NOT IN "
                            "(SELECT b.user_2 AS friendID "
                            "FROM users a "
                            "JOIN network b ON a.id = b.user_1 "
                            "WHERE a.id = ?);", user_id, user_id)
        return {'data': [dict(zip(tuple(query.keys()), i)) for i in query.cursor]}


    @app.route('/vote', methods=['POST'])
    def vote():
        conn = db_connect.connect()  # connect to database
        if request.method == 'POST':  # this block is only entered when the form is submitted
            req_data = request.get_json()
            print(req_data)
            tweet_id = req_data['id']
            user_id = req_data['user_id']
            score = req_data['score']
            conn.execute("UPDATE user_votes SET down_votes = down_votes + 1 WHERE tweet_id = ?;", tweet_id)
            conn.execute("INSERT INTO voted (user_id, tweet_id, score) VALUES (?, ?, ?);", user_id, tweet_id, score)

            return {'message': 'Success'}
        else:
            return {'message': 'Error'}


    @socketio.on('my_event', namespace='/test')
    def test_message(message):
        emit('my_response', {'data': message['data']})
        print(message)


    if __name__ == '__main__':
        socketio.run(app, port=80, debug=True, host='0.0.0.0')

if not os.path.isfile("classifier.model"):
    train_model.trainModel()

importModel()
startServer()
    
