# -*- coding: utf-8 -*-
"""
Created on 2018/12/16 上午9:30

@author: mick.yi

训练frcnn

"""

import argparse
import sys
import os
import tensorflow as tf
import keras
from faster_rcnn.config import current_config as config
from faster_rcnn.preprocess.input import VocDataset
from faster_rcnn.utils.generator import Generator
from faster_rcnn.layers import models
from keras.callbacks import TensorBoard, ModelCheckpoint


def set_gpu_growth(gpu_count):
    os.environ["CUDA_VISIBLE_DEVICES"] = ",".join([str(i) for i in range(gpu_count)])
    cfg = tf.ConfigProto(allow_soft_placement=True)  # because no supported kernel for GPU devices is available
    cfg.gpu_options.allow_growth = True
    session = tf.Session(config=cfg)
    keras.backend.set_session(session)


def get_call_back(stage):
    """
    定义call back
    :return:
    """
    checkpoint = ModelCheckpoint(filepath='/tmp/frcnn-' + stage + '.{epoch:03d}.h5',
                                 monitor='acc',
                                 verbose=1,
                                 save_best_only=False,
                                 save_weights_only=True,
                                 period=5)

    log = TensorBoard(log_dir='log')
    return [checkpoint, log]


def train(m, train_layers, epochs, init_epochs, train_img_info, test_img_info):
    # 生成器
    train_gen = Generator(train_img_info,
                          config.IMAGE_INPUT_SHAPE,
                          config.BATCH_SIZE,
                          config.MAX_GT_INSTANCES,
                          horizontal_flip=config.USE_HORIZONTAL_FLIP,
                          random_crop=config.USE_RANDOM_CROP)
    # 生成器
    val_gen = Generator(test_img_info,
                        config.IMAGE_INPUT_SHAPE,
                        config.BATCH_SIZE,
                        config.MAX_GT_INSTANCES)
    # 层名匹配
    layer_regex = {
        # 网络头
        "heads": r"base_features|(rcnn\_.*)|(rpn\_.*)",
        # 指定的阶段开始
        "3+": r"base_features|(res3.*)|(bn3.*)|(res4.*)|(bn4.*)|(res5.*)|(bn5.*)|(mrcnn\_.*)|(rpn\_.*)|(fpn\_.*)",
        "4+": r"base_features|(res4.*)|(bn4.*)|(res5.*)|(bn5.*)|(mrcnn\_.*)|(rpn\_.*)|(fpn\_.*)",
        "5+": r"base_features|(res5.*)|(bn5.*)|(mrcnn\_.*)|(rpn\_.*)|(fpn\_.*)",
        # 所有层
        "all": ".*",
    }
    models.set_trainable(layer_regex[train_layers], m)

    loss_names = ["rpn_bbox_loss", "rpn_class_loss", "rcnn_bbox_loss", "rcnn_class_loss"]
    models.compile(m, config, loss_names)
    # # 增加个性化度量
    # layer = m.inner_model.get_layer('rpn_target')
    # metric_names = ['gt_num', 'positive_anchor_num', 'miss_match_gt_num', 'gt_match_min_iou']
    # models.add_metrics(m, metric_names, layer.output[-4:])
    #
    # layer = m.inner_model.get_layer('rcnn_target')
    # metric_names = ['rcnn_miss_match_gt_num']
    # models.add_metrics(m, metric_names, layer.output[-1:])

    # 训练
    m.fit_generator(train_gen.gen(),
                    epochs=epochs,
                    steps_per_epoch=len(train_img_info) // config.BATCH_SIZE,
                    verbose=1,
                    initial_epoch=init_epochs,
                    validation_data=val_gen.gen(),
                    validation_steps=20,  # 小一点，不影响训练速度太多
                    use_multiprocessing=True,
                    callbacks=get_call_back('rcnn'))


def main(args):
    set_gpu_growth(config.GPU_COUNT)
    dataset = VocDataset(config.voc_path, class_mapping=config.CLASS_MAPPING)
    dataset.prepare()
    train_img_info = [info for info in dataset.get_image_info_list() if info['type'] == 'trainval']  # 训练集
    print("train_img_info:{}".format(len(train_img_info)))
    test_img_info = [info for info in dataset.get_image_info_list() if info['type'] == 'test']  # 测试集
    print("test_img_info:{}".format(len(test_img_info)))
    m = models.frcnn(config, stage='train')
    # 加载预训练模型
    m.load_weights(config.pretrained_weights, by_name=True)
    m.summary()
    #
    train(m, 'heads', 20, 0, train_img_info, test_img_info)
    train(m, '3+', 60, 20, train_img_info, test_img_info)
    train(m, 'all', 80, 60, train_img_info, test_img_info)


if __name__ == '__main__':
    parse = argparse.ArgumentParser()
    parse.add_argument("--epochs", type=int, default=50, help="epochs")
    argments = parse.parse_args(sys.argv[1:])
    main(argments)
