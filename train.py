#!/usr/bin/python3

import argparse
import os
import random
import logging

import tensorflow as tf
import numpy as np
from PIL import Image

from unet import UNet
from script import resize

train_data_update_freq = 1
test_data_update_freq = 50
sess_save_freq = 100

model_name = "matting"

logging.basicConfig(level=logging.INFO)

# Parse Arguments
parser = argparse.ArgumentParser(description="Trains the unet")
parser.add_argument("data", type=str,
    help="Path to a folder containing data to train")
parser.add_argument("--lr", type=float, default=1.0,
    help="Learning rate used to optimize")
parser.add_argument("--nb_epoch", dest="nb_epoch", type=int, default=5,
    help="Number of training epochs")
parser.add_argument("--batch_size", dest="batch_size", type=int, default=4,
    help="Size of the batches used in training")
parser.add_argument('--checkpoint', type=int, default=None,
    help='Saved session checkpoint, -1 for latest.')
parser.add_argument('--logdir', default="log/" + model_name,
    help='Directory where logs should be written.')
args = parser.parse_args()

input_path = os.path.join(args.data, "input")
trimap_path = os.path.join(args.data, "trimap")
target_path = os.path.join(args.data, "target")
output_path = os.path.join(args.data, "output")

if not os.path.isdir(output_path):
    os.makedirs(output_path)

if not os.path.isdir(args.logdir):
    os.makedirs(args.logdir)

ids = [os.path.splitext(filename)[0].split('_') for filename in os.listdir(input_path)]
np.random.shuffle(ids)
split_point = int(round(0.99*len(ids))) #using 70% as training and 30% as Validation
train_ids = ids[0:split_point]
valid_ids = ids[split_point:len(ids)]

global_step = tf.get_variable('global_step', initializer=0, trainable=False)

def apply_trimap(images, output, alpha):
    masked_output = []
    for channel in range(4):
        masked_output.append(output[:,:,:,channel])
        masked_output[channel] = tf.where(alpha < 0.25, images[:,:,:,channel], masked_output[channel])
        masked_output[channel] = tf.where(alpha > 0.75, images[:,:,:,channel], masked_output[channel])
        masked_output[channel] = masked_output[channel]
    masked_output = tf.stack(masked_output, 3)
    return masked_output

input_images = tf.placeholder(tf.float32, shape=[None, 240, 180, 4])
target_images = tf.placeholder(tf.float32, shape=[None, 240, 180, 4])
model = UNet(4,4)
output = tf.sigmoid(tf.squeeze(model(input_images)))

masked_output = apply_trimap(target_images, output, input_images[:,:,:,3])
loss = tf.losses.mean_squared_error(target_images, output)

optimizer = tf.train.AdadeltaOptimizer(args.lr).minimize(loss, global_step=global_step)

init = tf.global_variables_initializer()
sess = tf.Session()
sess.run(init)

saver = tf.train.Saver()
if args.checkpoint is not None and os.path.exists(os.path.join(args.logdir, 'checkpoint')):
    if args.checkpoint == -1:#latest checkpoint
        saver.restore(sess, tf.train.latest_checkpoint(args.logdir))
    else:#Specified checkpoint
        saver.restore(sess, os.path.join(args.logdir, model_name+".ckpt-"+str(args.checkpoint)))
    logging.debug('Model restored to step ' + str(global_step.eval(sess)))


# from https://stackoverflow.com/questions/8290397/how-to-split-an-iterable-in-constant-size-chunks
def batch(iterable, n=1):
    l = len(iterable)
    for ndx in range(0, l, n):
        yield iterable[ndx:min(ndx + n, l)]


def load_batch(batch_ids):
    images, targets = [], []
    for i, j in batch_ids:
        input_filename = os.path.join(input_path, str(i) + '_' + str(j) + '.jpg')
        trimap_filename = os.path.join(trimap_path, str(i) + '_trimap.jpg')
        target_filename = os.path.join(target_path, str(i) + '.png')
        logging.debug(input_filename)
        logging.debug(trimap_filename)
        logging.debug(target_filename)
        image = resize(Image.open(input_filename), 4)
        trimap = resize(Image.open(trimap_filename), 4)
        target = resize(Image.open(target_filename), 4)

        image = np.array(image)
        trimap = np.array(trimap)[..., np.newaxis]
        image = np.concatenate((image, trimap), axis = 2).astype(np.float32) / 255

        target = np.array(target).astype(np.float32) / 255

        images.append(image)
        targets.append(target)

    return np.asarray(images), np.asarray(targets)


def test_step():
    total_loss = 0

    for batch_range in batch(valid_ids, args.batch_size):
        images, targets = load_batch(batch_range)

        l, o = sess.run([loss, masked_output], feed_dict={
            input_images: images,
            target_images: targets,
            })
        total_loss += l*args.batch_size

        for idx, (i,j) in enumerate(batch_range):
            image = Image.fromarray((o[idx,:,:,:] * 255).astype(np.uint8))
            image.save(os.path.join(output_path, str(i) + '.png'))

    logging.info('Validation Loss: {}'.format(total_loss / len(valid_ids)))


def train_step(batch_idx):
    batch_range = random.sample(train_ids, args.batch_size)

    images, targets = load_batch(batch_range)

    _, l = sess.run([optimizer, loss], feed_dict={
        input_images: np.array(images),
        target_images: np.array(targets),
        })

    if batch_idx % train_data_update_freq == 0:
        logging.info('Train Epoch: [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(
            (batch_idx+1) * args.batch_size, len(ids),
            100. * (batch_idx+1) * args.batch_size / len(ids), l))


while global_step.eval(sess) < args.nb_epoch * len(train_ids)/args.batch_size:
    batch_idx = global_step.eval(sess)
    train_step(batch_idx)
    batch_idx = global_step.eval(sess)

    if batch_idx % test_data_update_freq == 0:
        test_step()

    if batch_idx % sess_save_freq == 0:
        logging.debug('Saving model')
        saver.save(sess, os.path.join(args.logdir, model_name+".ckpt"), global_step=batch_idx)

