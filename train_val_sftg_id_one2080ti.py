"""
单卡训练+测试代码是否能够正常运转+非正式组
代码描述：SFTG平台数据+带有平台ID+Fix_Attention_BaseLine+Adam=0.01+all_batch_size=64

"""
import torch
import random
import numpy as np
import torch.optim as optim
import pandas as pd

from Fusion_Net_revise_attention_id import RankNet, init_weights
from Dataset_pair_train_id import MyDatasetTrain
from Dataset_pair_val_id import MyDatasetVal
from torch.utils.data import DataLoader


def seed_torch(seed=1):
    random.seed(seed)  # Python random module
    # os.environ['PYTHONHASHSEED'] = str(seed)  # 为了禁止hash随机化，使得实验可复现
    np.random.seed(seed)  # Numpy module
    torch.manual_seed(seed)  # 为CPU设置随机数种子
    torch.cuda.manual_seed(seed)  # 为当前GPU设置随机数种子
    torch.cuda.manual_seed_all(seed)  # 为所有GPU设置随机数种子
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


seed_torch()


def main():
    global train_loss_list
    global train_acc_list
    global val_loss_list
    global val_acc_list

    train_loss_list = []
    train_acc_list = []
    val_loss_list = []
    val_acc_list = []

    epochs = 31
    # 导入训练集
    my_dataset = MyDatasetTrain("./SFTG_CTR_label_pair_train_id.csv")
    train_loader = DataLoader(dataset=my_dataset, batch_size=64, drop_last=True)
    train_num = len(my_dataset)

    # 导入验证集
    my_dataset_val = MyDatasetVal("./SFTG_CTR_label_pair_val_id.csv")
    val_loader = DataLoader(dataset=my_dataset_val, batch_size=64, drop_last=True)
    val_num = len(my_dataset_val)

    # 实例化模型
    model_rank = RankNet()
    model_rank = model_rank.double()
    model_rank = model_rank.train()

    # 参数初始化
    model_rank.apply(init_weights)

    # 将模型丢到cuda训练
    if torch.cuda.is_available():
        print("cuda是否能够使用:", torch.cuda.is_available())
        model_rank = model_rank.cuda()

    # 损失函数
    criterion = torch.nn.BCELoss()
    if torch.cuda.is_available():
        criterion = criterion.cuda()

    # 优化器
    # optimizer = optim.Adadelta(model_rank.parameters(), lr=0.008)
    optimizer = optim.Adam(model_rank.parameters(), lr=0.01)

    # 训练
    for epoch in range(1, epochs):
        # train
        pre_right = 0  # 统计正确个数
        train_steps = 0  # 计数,运行到第几个batch
        running_loss_train = 0.0
        model_rank = model_rank.train()  # 模型重新设置为训练模式

        # train
        for v1_train, a1_train, v2_train, a2_train, ctr_label, id_pair in iter(train_loader):
            # 用来计数,当前是第几个train_batch
            train_steps += 1
            print("当前运行是train第{}个epoch中,第{}个batch".format(epoch, train_steps))
            optimizer.zero_grad()

            # 将数据丢到cuda上进行训练
            if torch.cuda.is_available():
                v1_train = v1_train.cuda()
                a1_train = a1_train.cuda()
                v2_train = v2_train.cuda()
                a2_train = a2_train.cuda()
                ctr_label = ctr_label.cuda()
                id_pair = id_pair.cuda()
            output_train = model_rank(v1_train, a1_train, v2_train, a2_train, id_pair)

            # 计算训练集的acc
            for i in range(64):
                if output_train[1][i] > output_train[2][i]:
                    p = 1
                elif output_train[1][i] < output_train[2][i]:
                    p = 0
                else:
                    p = 0.5

                # 与Label进行比较，并且统计预测正确的个数
                if p == ctr_label[i]:
                    pre_right += 1
            print("第{}个batch:COMPARE_FINISH!".format(train_steps))
            # print("当前预测正确的个数是:{}".format(pre_right))

            # 获取广告对相应的Label(真实概率) 预处理(在dim=1增加一个维度，确保后续计算能够顺利进行)
            real_probability = torch.unsqueeze(ctr_label.to(torch.double), dim=1)
            # print(output)
            # print(real_probability.shape)
            # print('+++++++++')

            # 将预测概率和真实概率送入损失函数中,计算loss
            loss = criterion(output_train[0], real_probability)
            # print("第{}个batch的loss是{}".format(train_steps, loss))
            loss.backward()
            optimizer.step()

            # 计算每个epoch的平均loss
            running_loss_train += loss.item()
        epoch_loss_train = running_loss_train / train_steps
        train_loss_list.append(epoch_loss_train)
        print("**训练集上第{}个epoch的平均loss是:{}**".format(epoch, epoch_loss_train))

        # 计算准确率
        acc_train = pre_right / train_num
        train_acc_list.append(acc_train)
        print("**训练集上第{}个epoch的准确率是:{}**".format(epoch, acc_train))

        # validation
        if epoch % 3 == 0:
            acc_val = 0
            pre_right_val = 0
            val_steps = 0
            model_rank = model_rank.eval()
            running_loss_val = 0.0
            with torch.no_grad():
                for v1_val, a1_val, v2_val, a2_val, ctr_label_val, id_pair_val in iter(val_loader):

                    # 用来记录第几个val_batch
                    val_steps += 1
                    print("当前运行是val第{}个epoch中，第{}个batch".format(epoch, val_steps))

                    # 将验证集数据丢到CUDA上
                    if torch.cuda.is_available():
                        v1_val = v1_val.cuda()
                        a1_val = a1_val.cuda()
                        v2_val = v2_val.cuda()
                        a2_val = a2_val.cuda()
                        ctr_label_val = ctr_label_val.cuda()
                        id_pair_val = id_pair_val.cuda()
                    output_val = model_rank(v1_val, a1_val, v2_val, a2_val, id_pair_val)

                    # 计算val_acc
                    for i in range(64):
                        if output_val[1][i] > output_val[2][i]:
                            p = 1
                        elif output_val[1][i] < output_val[2][i]:
                            p = 0
                        else:
                            p = 0.5

                        # 与Label进行比较，并且统计预测正确的个数
                        if p == ctr_label_val[i]:
                            pre_right_val += 1
                    print("第{}个batch:COMPARE_FINISH!".format(val_steps))

                    # 获取广告对相应的Label(真实概率) 预处理(在dim=1增加一个维度，确保后续计算能够顺利进行)
                    real_probability_val = torch.unsqueeze(ctr_label_val.to(torch.double), dim=1)

                    # 计算val_loss
                    loss_val = criterion(output_val[0], real_probability_val)
                    # print("VAL 第{}个batch的loss{}".format(val_steps, loss_val))

                    # 计算val上epoch的平均loss
                    running_loss_val += loss_val.item()
                epoch_loss_val = running_loss_val / val_steps
                val_loss_list.append(epoch_loss_val)
                print("！！验证集上第{}个epoch的平均loss是:{}！！".format(epoch, epoch_loss_val))

                # 计算val上的准确率
                acc_val = pre_right_val / val_num
                val_acc_list.append(acc_val)
                print("！！验证集上第{}个epoch的准确率是:{}！！".format(epoch, acc_val))
        # 保存模型权重
        save_path = './Rank_net+SFTG+ID+Fix_BaseLine' + str(epoch) + '.pth'
        # save_path = './Rank_net+Snap+Dot' + str(epoch) + '.pth'
        torch.save(model_rank.state_dict(), save_path)

    # 生成SFTG_train_loss列表
    col_train_loss = ['train_loss_epoch']
    info_array_train_loss = np.array(train_loss_list)
    df = pd.DataFrame(info_array_train_loss, columns=col_train_loss)
    train_loss_path = './model_weight Adam=0.01&Fix_attention epoch=30/train_sftg_id_loss+fix_baseline+0.01.csv'
    # train_loss_path = './train_snap_loss+dot.csv'
    df.to_csv(train_loss_path, encoding='utf-8')

    # 生成SFTG_train_acc列表
    col_train_acc = ['train_acc_epoch']
    info_array_train_acc = np.array(train_acc_list)
    df = pd.DataFrame(info_array_train_acc, columns=col_train_acc)
    train_acc_path = './model_weight Adam=0.01&Fix_attention epoch=30/train_sftg_id_acc+fix_baseline+0.01.csv'
    # train_acc_path = './train_snap_acc+dot.csv'
    df.to_csv(train_acc_path, encoding='utf-8')

    # 生成SFTG_val_loss列表
    col_val_loss = ['val_loss_epoch']
    info_array_val_loss = np.array(val_loss_list)
    df = pd.DataFrame(info_array_val_loss, columns=col_val_loss)
    val_loss_path = './model_weight Adam=0.01&Fix_attention epoch=30/val_sftg_id_loss+fix_baseline+0.01.csv'
    # val_loss_path = './val_snap_loss+dot.csv'
    df.to_csv(val_loss_path, encoding='utf-8')

    # 生成SFTG_val_acc列表
    col_val_acc = ['val_acc_epoch']
    info_array_val_acc = np.array(val_acc_list)
    df = pd.DataFrame(info_array_val_acc, columns=col_val_acc)
    val_acc_path = './model_weight Adam=0.01&Fix_attention epoch=30/val_sftg_id_acc+fix_baseline+0.01.csv'
    # val_acc_path = './val_snap_acc+dot.csv'
    df.to_csv(val_acc_path, encoding='utf-8')


if __name__ == '__main__':
    main()
# val_list.append(running_loss_val / val_steps)
