# coding: utf-8


# Catch passed auguments from run script.
import argparse, sys
parser = argparse.ArgumentParser()
parser.add_argument("--data_dir", type=str, default="data")
parser.add_argument("--working_dir", type=str, default="tmp")
parser.add_argument("--data_name", type=str, default="beer_reviews_single_aspect")
parser.add_argument("--embedding_name", type=str, default="glove/glove.6B.100d.txt")
parser.add_argument("--model_type", type=str, default="RNN")
parser.add_argument("--cell_type", type=str, default="GRU")
parser.add_argument("--hidden_dim", type=int, default=400)
parser.add_argument("--embedding_dim", type=int, default=100)
parser.add_argument("--kernel_size", type=int, default=5)
parser.add_argument("--layer_num", type=int, default=1)
parser.add_argument("--fine_tuning", type=bool, default=False)
parser.add_argument("--z_dim", type=int, default=2)
parser.add_argument("--gumbel_temprature", type=float, default=0.1)
parser.add_argument("--cuda", type=bool, default=True)
parser.add_argument("--batch_size", type=int, default=32)
parser.add_argument("--mlp_hidden_dim", type=int, default=50)
parser.add_argument("--dropout_rate", type=float, default=0.4)
parser.add_argument("--use_relative_pos", type=bool, default=True)
parser.add_argument("--max_pos_num", type=int, default=20)
parser.add_argument("--pos_embedding_dim", type=int, default=-1)
parser.add_argument("--fixed_classifier", type=bool, default=True)
parser.add_argument("--fixed_E_anti", type=bool, default=True)
parser.add_argument("--lambda_sparsity", type=float, default=1.0)
parser.add_argument("--lambda_continuity", type=float, default=1.0)
parser.add_argument("--lambda_anti", type=float, default=1.0)
parser.add_argument("--lambda_pos_reward", type=float, default=0.1)
parser.add_argument("--exploration_rate", type=float, default=0.05)
parser.add_argument("--highlight_percentage", type=float, default=0.3)
parser.add_argument("--highlight_count", type=int, default=8)
parser.add_argument("--count_tokens", type=int, default=8)
parser.add_argument("--count_pieces", type=int, default=4)
parser.add_argument("--lambda_acc_gap", type=float, default=1.2)
parser.add_argument("--label_embedding_dim", type=int, default=400)
parser.add_argument("--game_mode", type=str, default="3player")
parser.add_argument("--margin", type=float, default=0.2)
parser.add_argument("--lm_setting", type=str, default="multiple")
parser.add_argument("--lambda_lm", type=float, default=1.0)
parser.add_argument("--ngram", type=int, default=4)
parser.add_argument("--with_lm", type=bool, default=False)
parser.add_argument("--batch_size_ngram_eval", type=int, default=5)
parser.add_argument("--lr", type=float, default=0.001)
parser.add_argument("--model_prefix", type=str, default="tmp")
parser.add_argument("--pre_trained_model_prefix", type=str, default="pre_trained_cls.model")
args, extras = parser.parse_known_args()
print("Arguments:", args)
args.extras = extras
args.command = " ".join(["python"] + sys.argv)

# Torch.
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable

# (achtung-gpu) Use the 2nd GPU chip.
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "1"

# Set random seeds.
import numpy as np
import random
torch.manual_seed(0)  # Set random seeds.
np.random.seed(0)
random.seed(0)

# Import specified dataset loader.
import importlib
dataset = importlib.import_module("datasets." + args.data_name)

from models.rationale_3players import HardRationale3PlayerClassificationModelForEmnlp
from utils.trainer_utils import copy_classifier_module, evaluate_rationale_model_glue_for_acl

from collections import deque
from tqdm import tqdm

"""
class Argument():
    def __init__(self):
        self.model_type = 'RNN'
        self.cell_type = 'GRU'
        self.hidden_dim = 400
        self.embedding_dim = 100
        self.kernel_size = 5
        self.layer_num = 1
        self.fine_tuning = False
        self.z_dim = 2
        self.gumbel_temprature = 0.1
        self.cuda = True
        self.batch_size = 32
        self.mlp_hidden_dim = 50
        self.dropout_rate = 0.4
        self.use_relative_pos = True
        self.max_pos_num = 20
        self.pos_embedding_dim = -1
        self.fixed_classifier = True
        self.fixed_E_anti = True
        self.lambda_sparsity = 1.0
        self.lambda_continuity = 1.0
        self.lambda_anti = 1.0
        self.lambda_pos_reward = 0.1
        self.exploration_rate = 0.05
        self.highlight_percentage = 0.3
        self.highlight_count = 8
        self.count_tokens = 8
        self.count_pieces = 4
        self.lambda_acc_gap = 1.2
        self.label_embedding_dim = 400
        self.game_mode = '3player'
        self.margin = 0.2
        self.lm_setting = 'multiple' # 'single'
        self.lambda_lm = 1.0 # 100.0
        self.ngram = 4
        self.with_lm = False
        self.batch_size_ngram_eval = 5
        self.lr=0.001
        self.working_dir = run_args.working_dir
        self.model_prefix = 'tmp.%s.highlight%.2f.cont%.2f'%(self.game_mode, self.highlight_percentage, self.lambda_continuity)
        self.pre_trained_model_prefix = 'pre_trained_cls.model'

args = Argument()
"""
args_dict = vars(args)
print(args_dict)
# embedding_size = 100

# Load data.
data_path = os.path.join(args.data_dir, args.data_name)
beer_data = dataset.DataLoader(data_path, score_threshold=0.6, split_ratio=0.1)

# TODO: handle save/load vocab here, for saving vocab, use the following, for loading, load embedding from checkpoint
embedding_path = os.path.join(args.data_dir, args.embedding_name)
# embeddings = beer_data.initial_embedding(args.embedding_dim, embedding_path)
embeddings = beer_data.initial_embedding(args.embedding_dim)

args.num_labels = len(beer_data.label_vocab)
print('num_labels: ', args.num_labels)
print(beer_data.idx2label)

classification_model = HardRationale3PlayerClassificationModelForEmnlp(embeddings, args)

if args.cuda:
    classification_model.cuda()

print(classification_model)

if 'count_tokens' in args_dict and 'count_pieces' in args_dict:
    classification_model.count_tokens = args.count_tokens
    classification_model.count_pieces = args.count_pieces


train_losses = []
train_accs = []
dev_accs = [0.0]
dev_anti_accs = [0.0]
dev_cls_accs = [0.0]
test_accs = [0.0]
best_dev_acc = 0.0

eval_accs = [0.0]
eval_anti_accs = [0.0]

args.load_pre_cls = False
args.load_pre_gen = False

# snapshot_path = os.path.join(args.working_dir, args.pre_trained_model_prefix + '.pt')
# classification_model = torch.load(snapshot_path)

classification_model.init_C_model()

if args.load_pre_cls:
    print('loading pre-trained the CLS')
    snapshot_path_enc = os.path.join(args.working_dir, args.pre_trained_model_prefix + '.encoder.tmp.pt')
    # torch.save(classification_model.generator.Classifier_enc, snapshot_path_enc)
    snapshot_path_pred = os.path.join(args.working_dir, args.pre_trained_model_prefix + '.predictor.tmp.pt')
    # torch.save(classification_model.generator.Classifier_pred, snapshot_path_pred)

    copy_classifier_module(classification_model.E_model, snapshot_path_enc, snapshot_path_pred)
    copy_classifier_module(classification_model.E_anti_model, snapshot_path_enc, snapshot_path_pred)
    
    copy_classifier_module(classification_model.C_model, snapshot_path_enc, snapshot_path_pred)

    print(classification_model)
if args.load_pre_gen:
    print('loading pre-trained the GEN+CLS')
    snapshot_path_gen = os.path.join(args.working_dir, args.model_prefix + '.train_gen.pt')
    classification_model = torch.load(snapshot_path_gen)


args.pre_train_cls = False
args.fixed_E_anti = False
classification_model.fixed_E_anti = args.fixed_E_anti
args.with_lm = False
args.lambda_lm = 1.0

print('training with game mode:', classification_model.game_mode)

train_losses = []
train_accs = []
dev_accs = [0.0]
dev_anti_accs = [0.0]
dev_cls_accs = [0.0]
test_accs = [0.0]
test_anti_accs = [0.0]
test_cls_accs = [0.0]
best_dev_acc = 0.0
best_test_acc = 0.0
num_iteration = 10
display_iteration = 10
test_iteration = 10

eval_accs = [0.0]
eval_anti_accs = [0.0]

queue_length = 200
z_history_rewards = deque(maxlen=queue_length)
z_history_rewards.append(0.)

classification_model.init_optimizers()
classification_model.init_rl_optimizers()
classification_model.init_reward_queue()

old_E_anti_weights = classification_model.E_anti_model.predictor._parameters['weight'][0].cpu().data.numpy()

for i in tqdm(range(num_iteration)):
    classification_model.train()
#     supervise_optimizer.zero_grad()
#     rl_optimizer.zero_grad()

#     classification_model.lambda_sparsity = (float(i) / num_iteration) * args.lambda_sparsity
#     classification_model.highlight_percentage = args.highlight_percentage + (1.0 - args.highlight_percentage) * (1 - (float(i) / num_iteration))

    # sample a batch of data
    x_mat, y_vec, x_mask = beer_data.get_train_batch(batch_size=args.batch_size, sort=True)

    batch_x_ = Variable(torch.from_numpy(x_mat))
    batch_m_ = Variable(torch.from_numpy(x_mask)).type(torch.FloatTensor)
    batch_y_ = Variable(torch.from_numpy(y_vec))
    if args.cuda:
        batch_x_ = batch_x_.cuda()
        batch_m_ = batch_m_.cuda()
        batch_y_ = batch_y_.cuda()
        
    z_baseline = Variable(torch.FloatTensor([float(np.mean(z_history_rewards))]))
    if args.cuda:
        z_baseline = z_baseline.cuda()
    
    if not args.with_lm:
        losses, predict, anti_predict, z, z_rewards, continuity_loss, sparsity_loss = classification_model.train_one_step(
            batch_x_, batch_y_, z_baseline, batch_m_, with_lm=False)
    else:
        losses, predict, anti_predict, z, z_rewards, continuity_loss, sparsity_loss = classification_model.train_one_step(
            batch_x_, batch_y_, z_baseline, batch_m_, with_lm=True)
    
    z_batch_reward = np.mean(z_rewards.cpu().data.numpy())
    z_history_rewards.append(z_batch_reward)

    # calculate classification accuarcy
    _, y_pred = torch.max(predict, dim=1)
    
    acc = np.float((y_pred == batch_y_).sum().cpu().data) / args.batch_size
    train_accs.append(acc)

    train_losses.append(losses['e_loss'])
    
    if args.fixed_E_anti == True:
        new_E_anti_weights = classification_model.E_anti_model.predictor._parameters['weight'][0].cpu().data.numpy()
        assert (old_E_anti_weights == new_E_anti_weights).all(), 'E anti model changed'
    
    if (i+1) % display_iteration == 0:
        print('sparsity lambda: %.4f'%(classification_model.lambda_sparsity))
        print('highlight percentage: %.4f'%(classification_model.highlight_percentage))
        print('supervised_loss %.4f, sparsity_loss %.4f, continuity_loss %.4f'%(losses['e_loss'], torch.mean(sparsity_loss).cpu().data, torch.mean(continuity_loss).cpu().data))
        if args.with_lm:
            print('lm prob: %.4f'%losses['lm_prob'])
        y_ = y_vec[2]
        pred_ = y_pred.data[2]
        x_ = x_mat[2,:]
        if len(z.shape) == 3:
            z_ = z.cpu().data[2,pred_,:]
        else:
            z_ = z.cpu().data[2,:]

        z_b = torch.zeros_like(z)
        z_b_ = z_b.cpu().data[2,:]
        print('gold label:', beer_data.idx2label[y_], 'pred label:', beer_data.idx2label[pred_.item()])
        beer_data.display_example(x_, z_)

    if (i+1) % test_iteration == 0:
        new_best_dev_acc = evaluate_rationale_model_glue_for_acl(classification_model, beer_data, args, dev_accs, dev_anti_accs, dev_cls_accs, best_dev_acc, print_train_flag=False)
        
        new_best_test_acc = evaluate_rationale_model_glue_for_acl(classification_model, beer_data, args, test_accs, test_anti_accs, test_cls_accs, best_test_acc, print_train_flag=False, eval_test=True)

        if new_best_dev_acc > best_dev_acc:
            best_dev_acc = new_best_dev_acc
            snapshot_path = os.path.join(args.working_dir, args.model_prefix + '.state_dict.bin')
            print('new best dev:', new_best_dev_acc, 'model saved at', snapshot_path)
            torch.save(classification_model.state_dict(), snapshot_path)

        if new_best_test_acc > best_test_acc:
            best_test_acc = new_best_test_acc
