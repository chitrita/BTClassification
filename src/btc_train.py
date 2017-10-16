# Brain Tumor Classification
# Script for Training Models
# Author: Qixun Qu
# Create on: 2017/10/14
# Modify on: 2017/10/14

#     ,,,         ,,,
#   ;"   ';     ;'   ",
#   ;  @.ss$$$$$$s.@  ;
#   `s$$$$$$$$$$$$$$$'
#   $$$$$$$$$$$$$$$$$$
#  $$$$P""Y$$$Y""W$$$$$
#  $$$$  p"$$$"q  $$$$$
#  $$$$  .$$$$$.  $$$$'
#   $$$DaU$$O$$DaU$$$'
#    '$$$$'.^.'$$$$'
#       '&$$$$$&'


import os
import shutil
import numpy as np
import tensorflow as tf
from btc_models import BTCModels
from btc_parameters import parameters
from btc_tfrecords import BTCTFRecords
from btc_settings import PCW, PCG, PCY, PCB, PCC


class BTCTrain():

    def __init__(self, net, paras, save_path):
        '''__INIT__
        '''

        # Basic settings
        self.net = net
        self.mode = "train"
        self.models = BTCModels()
        self.tfr = BTCTFRecords()

        self.model_path = os.path.join(save_path, net)
        if not os.path.isdir(self.model_path):
            os.makedirs(self.model_path)

        self.train_path = paras["train_path"]
        self.validate_path = paras["validate_path"]

        self.classes_num = paras["classes_num"]
        self.patch_shape = paras["patch_shape"]
        self.capacity = paras["capacity"]
        self.min_after_dequeue = paras["min_after_dequeue"]

        # Hyper-parameters
        self.batch_size = paras["batch_size"]
        self.num_epoches = paras["num_epoches"]

        # Other settings
        self.tepoch_iters = self._get_epoch_iters(paras["train_num"])
        self.vepoch_iters = self._get_epoch_iters(paras["validate_num"])

        # print("Train iters: ", self.tepoch_iters)
        # print("Validate iters: ", self.vepoch_iters)

        return

    def _get_epoch_iters(self, num):
        '''_GET_EPOCH_ITERS
        '''

        index = np.arange(1, self.num_epoches + 1)
        iters_per_epoch = np.floor(index * (num / self.batch_size))

        return iters_per_epoch.astype(np.int64)

    def _load_data(self, tfrecord_path):
        '''_LOAD_DATA
        '''

        return self.tfr.decode_tfrecord(path=tfrecord_path,
                                        batch_size=self.batch_size,
                                        num_epoches=self.num_epoches,
                                        patch_shape=self.patch_shape,
                                        capacity=self.capacity,
                                        min_after_dequeue=self.min_after_dequeue)

    def train(self):
        '''TRAIN
        '''

        x = tf.placeholder(tf.float32, [None] + self.patch_shape)
        y_input_classes = tf.placeholder(tf.int64, [None])
        drop_rate = tf.placeholder(tf.float32)

        y_output_logits = self.models.cnn(x, drop_rate)
        y_input_onehot = tf.one_hot(indices=y_input_classes, depth=self.classes_num)

        loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(labels=y_input_onehot,
                                                                      logits=y_output_logits))

        y_output_classes = tf.argmax(input=y_output_logits, axis=1)
        correction_prediction = tf.equal(y_output_classes, y_input_classes)
        accuracy = tf.reduce_mean(tf.cast(correction_prediction, tf.float32))

        update_ops = tf.get_collection(tf.GraphKeys.UPDATE_OPS)
        with tf.control_dependencies(update_ops):
            train_op = tf.train.AdamOptimizer(1e-2).minimize(loss)

        tra_volumes, tra_labels = self._load_data(self.train_path)
        val_volumes, val_labels = self._load_data(self.validate_path)

        init = tf.group(tf.local_variables_initializer(),
                        tf.global_variables_initializer())

        # Create a saver to save model while training
        saver = tf.train.Saver()

        sess = tf.InteractiveSession()
        sess.run(init)

        coord = tf.train.Coordinator()
        threads = tf.train.start_queue_runners(sess=sess, coord=coord)

        tra_iters, one_tra_iters, val_iters, epoch_no = 0, 0, 0, 0

        print(PCB + "Training and Validating model ...\n" + PCW)
        tloss_list, taccuracy_list = [], []
        try:
            while not coord.should_stop():
                tx, ty = sess.run([tra_volumes, tra_labels])
                tra_fd = {x: tx, y_input_classes: ty, drop_rate: 0.5}
                tloss = loss.eval(feed_dict=tra_fd)
                taccuracy = accuracy.eval(feed_dict=tra_fd)
                tloss_list.append(tloss)
                taccuracy_list.append(taccuracy)

                tra_iters += 1
                one_tra_iters += 1
                print((PCG + "[Epoch {}] ").format(epoch_no + 1),
                      "Train Step {}: ".format(one_tra_iters),
                      "Loss: {0:.10f}, ".format(tloss),
                      ("Accuracy: {0:.10f}" + PCW).format(taccuracy))

                if tra_iters % self.tepoch_iters[epoch_no] == 0:
                    vloss_list, vaccuracy_list = [], []
                    while val_iters < self.vepoch_iters[epoch_no]:
                        vx, vy = sess.run([val_volumes, val_labels])
                        val_fd = {x: vx, y_input_classes: vy, drop_rate: 0.0}
                        vloss_list.append(loss.eval(feed_dict=val_fd))
                        vaccuracy_list.append(accuracy.eval(feed_dict=val_fd))
                        val_iters += 1

                    tloss_mean = np.mean(tloss_list)
                    taccuracy_mean = np.mean(taccuracy_list)
                    tloss_list, taccuracy_list = [], []

                    print((PCY + "[Epoch {}] ").format(epoch_no + 1),
                          "Train Stage: ",
                          "Mean Loss: {0:.10f}, ".format(tloss_mean),
                          ("Mean Accuracy: {0:.10f}" + PCW).format(taccuracy_mean))

                    vloss_mean = np.mean(vloss_list)
                    vaccuracy_mean = np.mean(vaccuracy_list)

                    print((PCY + "[Epoch {}] ").format(epoch_no + 1),
                          "Validate Stage: ",
                          "Mean Loss: {0:.10f}, ".format(vloss_mean),
                          ("Mean Accuracy: {0:.10f}" + PCW).format(vaccuracy_mean))

                    ckpt_dir = os.path.join(self.model_path, "epoch-" + str(epoch_no + 1))
                    if os.path.isdir(ckpt_dir):
                        shutil.rmtree(ckpt_dir)
                    os.makedirs(ckpt_dir)

                    save_path = os.path.join(ckpt_dir, self.net)
                    saver.save(sess, save_path, global_step=epoch_no + 1)
                    print((PCC + "[Epoch {}] ").format(epoch_no + 1),
                          ("Model was saved in: {}\n" + PCW).format(ckpt_dir))

                    epoch_no += 1
                    one_tra_iters = 0

                sess.run(train_op, feed_dict=tra_fd)

        except tf.errors.OutOfRangeError:
            print(PCB + "Training has stopped." + PCW)
        finally:
            coord.request_stop()

        coord.join(threads)
        sess.close()

        return


if __name__ == "__main__":

    parent_dir = os.path.dirname(os.getcwd())
    save_path = os.path.join(parent_dir, "models")

    btc = BTCTrain("cnn", parameters, save_path)
    btc.train()
