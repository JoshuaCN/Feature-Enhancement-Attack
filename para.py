# -*- coding: utf-8 -*-
"""Trains a convolutional neural network on the MNIST dataset, then attacks it."""

from cleverhans.plot.pyplot_image import grid_visual
from cleverhans.attacks import CarliniWagnerL2 as CW_hans, SaliencyMapMethod as JSMA_hans
from cleverhans.utils_keras import KerasModelWrapper
from metrics import *
from train import create_lenet_model, create_cnn_model
from relattack_batch import *
from art.attacks.carlini import CarliniL2Method as CW_2, CarliniLInfMethod as CW_inf
from art.attacks.projected_gradient_descent import ProjectedGradientDescent as PGD_art
from keras.datasets.mnist import load_data as load_mnist
from keras.datasets.cifar10 import load_data as load_cifar10
from art.classifiers import KerasClassifier
import tensorflow as tf
import keras
import time
import numpy as np ; na = np.newaxis


Targeted = False
Defense = False
Show = False
Transfer = False
# Gamma = np.arange(0.01,0.1,0.005)
Gamma = [0.1]
Batch_Size = 200
# m = [3, 2, 1, 18, 4, 8, 11, 0, 61, 7]
m = range(100)
NORM = 0
EPS = 0.1
N = 20
dataset = [
        'mnist',
        # 'cifar10',
]
attacks = [

            # 'SA',
            # 'FEA',
            # 'JSMA_p',
            'JSMA_n'

            #  'PGD_art',
            # 'CW_art',
            # 'CW_hans',
]


# Create TF session and set as Keras backend session
sess = tf.Session()
keras.backend.set_session(sess)


if dataset == ['mnist']:
    (_, _), (X, Y) = load_mnist()
    X = np.expand_dims(X, -1)
    X = X[m, ...]
    Y = Y[m]
    model = create_lenet_model(X.shape[1:])
    model.load_weights('./models/mnist.h5')

else:
    (_, _), (X, Y) = load_cifar10()
    X = X[m, ...]
    Y = Y[m]
    model = create_cnn_model(X.shape[1:])
    model.load_weights('./models/cifar10.h5')

X = X / 127.5 - 1
art = KerasClassifier(clip_values=(-1., 1.), model=model)
clever = KerasModelWrapper(model)
(img_rows, img_cols, nchannels) = X.shape[1:4]
time_cost = np.zeros([4, len(Gamma)])
succ_rate = np.zeros([4, len(Gamma)])
measurements = np.zeros([4, len(Gamma), 4])
for i in np.arange(len(Gamma)):
    print('Proceding Gamma=%.3f' % Gamma[i])
    if 'SA' in attacks:
        start = time.time()
        if not Targeted:
            SA_X = relevance(model, X, 'gradient', Gamma[i], y=None, batch_size=Batch_Size)
        else:
            SA_X = np.zeros([np.size(m), 10, img_rows, img_cols, nchannels])
            for target in range(10):
                adv_x = relevance(model, X, 'gradient', Gamma[i], y=target, batch_size=Batch_Size)
                SA_X[:, target] = adv_x
            SA_X = SA_X.reshape([10 * np.size(m), img_rows, img_cols, nchannels])
        end = time.time()
        time_cost[0,i] = end-start
        succ_rate[0,i], measurements[0, i] = evaluate(model, X, SA_X, targeted=Targeted)

        if Defense:
            defenses(model, X, SA_X, FS=True, SS=True)
        if Transfer:
            transfer(X, SA_X)
        if Show:
            SA_X = (SA_X + 1)/2
            grid_visual(np.reshape(SA_X, (SA_X.shape[0] // 10, 10, img_rows, img_cols, nchannels)))

    if 'FEA' in attacks:
        start = time.time()
        if not Targeted:
            FEA_X = relevance(model, X, 'lrp.z', Gamma[i], y=None, batch_size=Batch_Size, norm=NORM, n=N, eps=EPS)
        else:
            FEA_X = np.zeros([np.size(m), 10, img_rows, img_cols, nchannels])
            for target in range(10):
                adv_x = relevance(model, X, 'lrp.z', Gamma[i], y=target, batch_size=Batch_Size, norm=NORM, n=N, eps=EPS)
                FEA_X[:, target] = adv_x
            FEA_X = FEA_X.reshape([10 * np.size(m), img_rows, img_cols, nchannels])
        end = time.time()
        time_cost[1,i] = end-start
        succ_rate[1, i], measurements[1, i] = evaluate(model, X, FEA_X, targeted=Targeted)

        if Defense:
            defenses(model,X,FEA_X,FS=True,SS=True)
        if Transfer:
            transfer(X, FEA_X)
        if Show:
            FEA_X = (FEA_X + 1) / 2
            grid_visual(np.reshape(FEA_X, (FEA_X.shape[0] // 10, 10, img_rows, img_cols, nchannels)))

    if 'PGD_art' in attacks:
        pgd = PGD_art(art)
        if NORM == 2:
            pgd_params = {
                        'eps': 10.,
                        'eps_step': EPS,
                        'max_iter': Gamma,
                        'norm': 2,
                        'batch_size': Batch_Size,
                         }
        elif NORM == np.inf:
            pgd_params = {
                        'eps': 10.,
                        'eps_step': EPS,
                        'max_iter': Gamma,
                        'norm': np.inf,
                        'batch_size': Batch_Size,
                         }
        start = time.time()
        PGD_X = pgd.generate(X, **pgd_params)
        end = time.time()
        print('Time:%.1f' % (end-start))
        succ_rate, measurements = evaluate(model, X, PGD_X)
        print("\nPGD-%s success rate: %.2f%%" % (NORM, succ_rate * 100))
        print('\nMetrics:%.2f, %.2f, %.3f, %.3f' % (measurements[0:4]))
        if Defense:
            defenses(model,X,PGD_X,FS=True,SS=True)
        if Transfer:
            transfer(X, PGD_X)
        if Show:
            PGD_X = (PGD_X + 1) / 2
            grid_visual(np.reshape(PGD_X, (10, PGD_X.shape[0] // 10, img_rows, img_cols, nchannels)))

    if 'JSMA_p' in attacks:
        jsma_p = JSMA_hans(clever, sess=sess)
        jsma_params = {'theta': 2., 'gamma': Gamma[i],
                       'clip_min': -1., 'clip_max': 1., 'y_target': None
                       }
        start = time.time()
        if not Targeted:
            JSMA_p = np.zeros(X.shape)
            for batch_id in range(int(np.ceil(X.shape[0] / float(Batch_Size)))):
                JSMA_p[batch_id * Batch_Size:(batch_id + 1) * Batch_Size] = jsma_p.generate_np(X[batch_id * Batch_Size:(batch_id + 1) * Batch_Size], **jsma_params)
        else:
            JSMA_p = np.zeros([np.size(m), 10, img_rows, img_cols, nchannels])
            for batch_id in range(int(np.ceil(X.shape[0] / float(Batch_Size)))):
                for target in range(10):
                    one_hot_target = np.zeros((1, 10))
                    one_hot_target[0, target] = 1
                    jsma_params['y_target'] = one_hot_target
                    JSMA_p[batch_id * Batch_Size:(batch_id + 1) * Batch_Size, target, ...] = jsma_p.generate_np(
                        X[batch_id * Batch_Size:(batch_id + 1) * Batch_Size], **jsma_params)
            JSMA_p = JSMA_p.reshape([10 * np.size(m), img_rows, img_cols, nchannels])
        end = time.time()
        time_cost[2, i] = end - start
        succ_rate[2, i], measurements[2, i] = evaluate(model, X, JSMA_p, targeted=Targeted)

        if Defense:
            defenses(model, X, JSMA_p, FS=True, SS=True)
        if Transfer:
            transfer(X, JSMA_p)
        if Show:
            JSMA_p = (JSMA_p + 1) / 2
            grid_visual(np.reshape(JSMA_p, (JSMA_p.shape[0] // 10, 10, img_rows, img_cols, nchannels)))

    if 'JSMA_n' in attacks:
        jsma_n = JSMA_hans(clever, sess=sess)
        jsma_params = {'theta': -2., 'gamma': Gamma[i],
                       'clip_min': -1., 'clip_max': 1., 'y_target': None
                       }
        start = time.time()
        if not Targeted:
            JSMA_n = np.zeros(X.shape)
            for batch_id in range(int(np.ceil(X.shape[0] / float(Batch_Size)))):
                JSMA_n[batch_id * Batch_Size:(batch_id + 1) * Batch_Size] = jsma_n.generate_np(
                    X[batch_id * Batch_Size:(batch_id + 1) * Batch_Size], **jsma_params)
        else:
            JSMA_n = np.zeros([np.size(m), 10, img_rows, img_cols, nchannels])
            for batch_id in range(int(np.ceil(X.shape[0] / float(Batch_Size)))):
                for target in range(10):
                    one_hot_target = np.zeros((1, 10))
                    one_hot_target[0, target] = 1
                    jsma_params['y_target'] = one_hot_target
                    JSMA_n[batch_id * Batch_Size:(batch_id + 1) * Batch_Size, target, ...] = jsma_n.generate_np(
                        X[batch_id * Batch_Size:(batch_id + 1) * Batch_Size], **jsma_params)
            JSMA_n = JSMA_n.reshape([10 * np.size(m), img_rows, img_cols, nchannels])
        end = time.time()
        time_cost[3, i] = end - start
        succ_rate[3, i], measurements[3, i] = evaluate(model, X, JSMA_n, targeted=Targeted)

        if Defense:
            defenses(model, X, JSMA_n, FS=True, SS=True)
        if Transfer:
            transfer(X, JSMA_n)
        if Show:
            JSMA_n = (JSMA_n + 1) / 2
            grid_visual(np.reshape(JSMA_n, (JSMA_n.shape[0] // 10, 10, img_rows, img_cols, nchannels)))

    if 'CW_hans' in attacks:
        cw = CW_hans(clever, sess=sess)
        cw_params = {'binary_search_steps': 1,
                     'max_iterations': Gamma,
                     'learning_rate': 0.1,
                     'initial_const': 10,
                     'clip_min': -1.,
                     'clip_max': 1.,
                     'confidence': 0,
                     }
        start = time.time()
        CW_X = cw.generate_np(X, **cw_params)
        end = time.time()
        print('Time:%.1f' % (end - start))
        succ_rate, measurements = evaluate(model, X, CW_X)
        print("\nCW-%s success rate: %.2f%%" % (NORM, succ_rate * 100))
        print('\nMetrics:%.2f, %.2f, %.3f, %.3f' % (measurements[0:4]))
        if Defense:
            defenses(model,X,CW_X,FS=True,SS=True)
        if Transfer:
            transfer(X, CW_X)
        if Show:
            CW_X = (CW_X + 1) / 2
            grid_visual(np.reshape(CW_X, (10, CW_X.shape[0] // 10, img_rows, img_cols, nchannels)))

if dataset == ['mnist']:
    if not Targeted:
        np.savez('MNIST_untgt_1k.npz', gamma=Gamma, time=time_cost, succ=succ_rate, measure=measurements)
    else:
        np.savez('MNIST_tgt_1k.npz', gamma=Gamma, time=time_cost, succ=succ_rate, measure=measurements)
else:
    if not Targeted:
        np.savez('CIFAR10_untgt_1k.npz', gamma=Gamma, time=time_cost, succ=succ_rate, measure=measurements)
    else:
        np.savez('CIFAR10_tgt_1k.npz', gamma=Gamma, time=time_cost, succ=succ_rate, measure=measurements)

