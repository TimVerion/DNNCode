import os
import cv2
import numpy as np
import tensorflow as tf
import json
from tensorflow.python.framework import graph_util
# from nets import myCharClassifier
from nets import myCharClassifier

train_dir="D:/forTensorflow/charRecTrain/train/"#"D:/forTensorflow/charRecTrain/data/train/train/"
test_dir="D:/forTensorflow/charRecTrain/test/"#"D:/forTensorflow/charRecTrain/data/test/test/"
label_map_path= "label_map.json"

model_path="models/"
pb_path=os.path.join(model_path,"pb/")
ckpt_path=os.path.join(model_path,"ckpt/")

model_name="myCharClassifier"

support_image_extensions=[".jpg",".png",".jpeg",".bmp"]

charDict = {'0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9' : 9,
        'A': 10, 'B': 11, 'C': 12, 'D': 13, 'E': 14, 'F': 15, 'G': 16, 'H': 17, 'I': 18,
        'J': 19, 'K': 20, 'L': 21, 'M': 22, 'N': 23, 'O': 24, 'P': 25, 'Q': 26,'R': 27,
        'S': 28, 'T': 29, 'U': 30, 'V': 31, 'W': 32, 'X': 33, 'Y': 34, 'Z': 35}
is_specific_dict=True

total_epoch_num=10
batch_size=16
channals=1

snapshot=1000

input_width=28
input_height=28

def create_label_map(specific_dict=None):
    if specific_dict is not None:
        label_dict=specific_dict
    else:
        label_dict={}
        label_id=0
        labels=[]
        for label in os.listdir(train_dir):
            labels.append(label)
        labels.sort()
        for label in labels:
            label_dict[label]=label_id
            label_id+=1
    print("label_dict:",label_dict)
    with open(label_map_path,"w") as fw:
        label_map_str=json.dumps(label_dict,indent=4)
        fw.write(label_map_str)
    return label_dict

def load_label_map(specific_dict=None,is_specific=False):
    #指定label_dict
    if is_specific and specific_dict is not None:
        return create_label_map(specific_dict)
    #创建新label_map
    return create_label_map(None)

    #使用原旧的label_map
    # with open(label_map_path,"r") as fr:
    #     # label_dict=eval(fr.read())
    #     label_dict=json.load(fr)
    # return label_dict

label_dict=load_label_map(charDict,is_specific=is_specific_dict)

def get_images_path(image_dir):
    image_paths=[]
    labels=[]

    for label_str in os.listdir(image_dir):
        class_dir=os.path.join(image_dir,label_str)
        for file_name in os.listdir(class_dir):
            extension=os.path.splitext(file_name)[1].lower()
            if extension not in support_image_extensions:
                continue
            image_path=os.path.join(image_dir,label_str,file_name)
            image_paths.append(image_path)
            labels.append(label_dict[label_str])

    data_path_array=np.array([image_paths,labels])   #2xN大小,其中N是总样本数
    data_path_array=data_path_array.transpose()

    np.random.shuffle(data_path_array)
    image_paths=list(data_path_array[:,0])
    labels=data_path_array[:,1]

    #image_paths和labels都是列向量形式
    return np.array(image_paths),np.array(labels)

def next_batch(is_random_sample,indices,image_paths,labels):
    if is_random_sample:
        # np.random.choice(最大值,N) :从[0,最大值)中选择N个数,默认放回
        # np.random.choice(数组,N，replace=false) :从数组中选择N个数,replace=False不放回
        indices=np.random.choice(len(image_paths),batch_size)
    elif indices==None:
        print("Please assign indices in the mode of random sampling!")
        return None,None
    try:
        batch_image_paths=image_paths[indices]
        batch_labels=labels[indices]
    except Exception as e:
        print("list index out of range while next_batch!")
        return None,None


    image_id=0
    batch_images_data=[]
    for image_file_path in batch_image_paths:
        channal_flag=cv2.IMREAD_GRAYSCALE if channals==1 else cv2.IMREAD_COLOR

        # print(image_file_path, batch_labels[image_id])
        # input("kkk")

        image=cv2.imread(image_file_path,channal_flag)
        if image is None:
            batch_labels=np.delete(batch_labels,image_id,0)
            continue
        image_id+=1
        image_resized=cv2.resize(image,(input_width,input_height))

        image_np_resized=np.resize(image_resized,(input_width,input_height,channals))
        batch_images_data.append(image_np_resized)

    batch_images_data=np.array(batch_images_data)
    return batch_images_data,batch_labels

def train():
    input_placeholder=tf.placeholder(tf.float32,shape=[None,input_width,input_height,channals],name="inputs")
    labels_placeholder=tf.placeholder(tf.int32,shape=[None],name="labels")

    classModel=myCharClassifier.myCharClassifier(len(label_dict),is_regular=True)

    preprocessed_inputs=classModel.preprocess(input_placeholder)
    logits=classModel.inference(preprocessed_inputs)

    softmax_output,classes=classModel.postprocess(logits)
    softmax_output_=tf.identity(softmax_output,name="softmax_output")
    classes_= tf.identity(classes,name="classes")

    loss=classModel.loss(logits,labels_placeholder)
    accuarcy=tf.reduce_mean(tf.cast(tf.equal(classes,labels_placeholder),tf.float32))

    global_step = tf.Variable(0, trainable=False)
    learning_rate = tf.train.exponential_decay(0.025, global_step, 150, 0.9)
    optimizer = tf.train.MomentumOptimizer(learning_rate, 0.9)
    train_step = optimizer.minimize(loss, global_step)

    ckpt_saver=tf.train.Saver()

    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())

        total_iters_num=0
        for epoch_num in range(total_epoch_num):
            train_images_all,train_labels_all=get_images_path(train_dir)
            test_images_all,test_labels_all=get_images_path(test_dir)
            train_images_num =len(train_images_all)
            cur_epoch_iters_num=train_images_num//batch_size
            for iters_num in range(cur_epoch_iters_num):
                indices=range(train_images_num)[iters_num*batch_size:(iters_num+1)*batch_size]
                #batch_image原始是uint8类型，但是可以传给tf.float32的placeholder
                train_batch_image,train_batch_labels = next_batch(False,indices,train_images_all,train_labels_all)
                test_batch_image, test_batch_labels = next_batch(True,None, test_images_all, test_labels_all)

                if train_batch_image is None or test_batch_image is None:
                    continue
                train_dict = {input_placeholder: train_batch_image,labels_placeholder: train_batch_labels}
                test_dict = {input_placeholder: test_batch_image, labels_placeholder: test_batch_labels}

                sess.run(train_step,feed_dict=train_dict)

                _loss,_accuary,_learning_rate=sess.run([loss,accuarcy,learning_rate],feed_dict=train_dict)
                _test_accuary=sess.run([accuarcy],feed_dict=test_dict)

                total_iters_num+=1

                if total_iters_num%snapshot==0:
                    #保存PB
                    constant_graph=graph_util.convert_variables_to_constants(sess,sess.graph_def,["softmax_output"])
                    with tf.gfile.FastGFile(pb_path+model_name+"-"+str(total_iters_num)+".pb", mode="wb") as fw:
                        fw.write(constant_graph.SerializeToString())
                    #保存CKPT
                    ckpt_saver.save(sess,ckpt_path+model_name+".ckpt",global_step=total_iters_num)
                show_text="epoch:{},epoch-iters:{},total-iters:{},loss:{},accuarcy:{},lr:{},val:{}".format\
                             (epoch_num,iters_num+1,total_iters_num,_loss,_accuary,_learning_rate,_test_accuary)
                print(show_text)
if __name__=="__main__":
    train()