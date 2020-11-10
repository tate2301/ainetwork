import pickle
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
import numpy as np  # linear algebra
import pandas as pd  # data processing, CSV file I/O (e.g. pd.read_csv)

# 1: unreliable
# 0: reliable


train = pd.read_csv('train.csv')
train.info()
train = train.fillna(' leeg')
train['total'] = train['author'] + train['text']

count_vectorizer = CountVectorizer(ngram_range=(1, 2))
counts = count_vectorizer.fit_transform(train['total'].values)

classifier = MultinomialNB()
targets = train['label'].values
classifier.fit(counts, targets)

filename = 'classifier.model'
pickle.dump(classifier, open(filename, 'wb'))
pickle.dump(count_vectorizer, open('vectors.weights', 'wb'))