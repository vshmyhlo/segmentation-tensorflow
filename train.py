import tensorflow as tf
import losses
import unet
from data_loaders.shapes import Shapes
from dataset import build_dataset


def build_summary(image, labels, logits):
    labels = tf.argmax(labels, -1)
    labels = tf.expand_dims(labels, -1)

    logits = tf.argmax(logits, -1)
    logits = tf.expand_dims(logits, -1)

    tf.summary.image('image', image)
    tf.summary.image('mask_true', tf.image.convert_image_dtype(labels, tf.uint8))
    tf.summary.image('mask_pred', tf.image.convert_image_dtype(logits, tf.uint8))


# TODO: regularization, initialization

def model_fn(features, labels, mode, params):
    global_step = tf.train.get_or_create_global_step()
    training = mode == tf.estimator.ModeKeys.TRAIN

    net = unet.Unet(num_classes=params['data_loader'].num_classes + 1)
    logits = net(features['image'], training=training)
    loss = losses.segmentation_loss(labels=labels['mask'], logits=logits)

    if mode == tf.estimator.ModeKeys.TRAIN:
        optimizer = tf.train.AdamOptimizer()
        train_step = optimizer.minimize(loss, global_step=global_step)

        return tf.estimator.EstimatorSpec(mode, loss=loss, train_op=train_step)

    if mode == tf.estimator.ModeKeys.EVAL:
        mask = tf.argmax(labels['mask'], -1)
        predictions = tf.argmax(logits, -1)

        metrics = {'iou': tf.metrics.mean_iou(
            labels=mask, predictions=predictions, num_classes=params['data_loader'].num_classes + 1)}

        build_summary(features['image'], labels['mask'], logits)

        summary_hook = tf.train.SummarySaverHook(
            save_steps=2,
            # save_secs=60,
            # output_dir=self.job_dir + "/eval_core",
            summary_op=tf.summary.merge_all())

        return tf.estimator.EstimatorSpec(mode, loss=loss, eval_metric_ops=metrics, evaluation_hooks=[summary_hook])


def input_fn(params):
    ds = build_dataset(params['data_loader']).batch(params['batch_size']).prefetch(1)
    features, labels = ds.make_one_shot_iterator().get_next()

    return features, labels


def main():
    EPOCHS = 1000
    BATCH_SIZE = 8

    config = tf.estimator.RunConfig(
        model_dir='./tf_log',
        # save_checkpoints_steps=LOG_INTERVAL,
        save_summary_steps=100)

    estimator = tf.estimator.Estimator(
        model_fn=model_fn,
        params={
            'data_loader': Shapes('./shapes-dataset', BATCH_SIZE * 100, (224, 224)),
            'batch_size': BATCH_SIZE
        },
        config=config)

    for epoch in range(EPOCHS):
        estimator.train(input_fn)
        estimator.evaluate(input_fn, steps=10)


if __name__ == '__main__':
    main()
