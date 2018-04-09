#!/usr/bin/python3

# sub-parts of the U-Net model

import math

import tensorflow as tf

class inconv():
    def __init__(self, in_ch, out_ch):
        super(inconv, self).__init__()
        self.out_ch = out_ch



    def __call__(self, x):
        x = tf.layers.conv2d(x, filters=self.out_ch, kernel_size=3, padding="same")
        x = tf.contrib.layers.batch_norm(x)
        x = tf.nn.relu(x)
        x = tf.layers.conv2d(x, filters=self.out_ch, kernel_size=3, padding="same")
        x = tf.contrib.layers.batch_norm(x)
        x = tf.nn.relu(x)
        return x


class down():
    def __init__(self, in_ch, out_ch):
        super(down, self).__init__()
        self.out_ch = out_ch


    def __call__(self, x):
        x = tf.layers.max_pooling2d(x, pool_size=[2,2], strides=2)
        x = tf.layers.conv2d(x, filters=self.out_ch,
                kernel_size=3, padding="same")
        x = tf.contrib.layers.batch_norm(x)
        x = tf.nn.relu(x)
        x = tf.layers.conv2d(x, filters=self.out_ch,
                kernel_size=3, padding="same")
        x = tf.contrib.layers.batch_norm(x)
        x = tf.nn.relu(x)
        return x


class up():
    def __init__(self, in_ch, out_ch, bilinear=True):
        super(up, self).__init__()
        self.out_ch = out_ch

    def __call__(self, x1, x2):
        x1 = tf.layers.conv2d_transpose(x1, filters=self.out_ch,
            kernel_size=3, strides=(2, 2), padding="same")

        x1 = tf.image.pad_to_bounding_box(x1, 0, 0, x2.shape[1], x2.shape[2])

        x = tf.concat([x2, x1], axis=3)
        x = tf.layers.conv2d(x, filters=self.out_ch,
                kernel_size=3, padding="same")
        x = tf.contrib.layers.batch_norm(x)
        x = tf.nn.relu(x)
        x = tf.layers.conv2d(x, filters=self.out_ch,
                kernel_size=3, padding="same")
        x = tf.contrib.layers.batch_norm(x)
        x = tf.nn.relu(x)
        return x


class outconv():
    def __init__(self, in_ch, out_ch):
        super(outconv, self).__init__()
        self.out_ch = out_ch

    def __call__(self, x):
        x = tf.layers.conv2d(x, filters=self.out_ch, kernel_size=1)
        return x
