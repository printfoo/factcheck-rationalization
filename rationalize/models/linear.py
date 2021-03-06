# coding: utf-8


import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable


class Linear(nn.Module):
    """
    Bag of words linear classification model.
    """

    def __init__(self, embeddings, args):
        super(Linear, self).__init__()
        self.args = args
        self.use_cuda = args.cuda
        self.vocab_size, self.embedding_dim = embeddings.shape
        self.embed_layer = self._create_embed_layer(embeddings)
        
        # A linear layer that inputs embeddings and outputs predictions,
        # the output is a scalar 0-|label| pointing to a label.
        self.linear = torch.nn.Linear(in_features=self.embedding_dim,
                                      out_features=args.num_labels)

        self.opt = torch.optim.SGD(self.parameters(), lr=args.lr)
        self.pred_loss = nn.CrossEntropyLoss()


    def _create_embed_layer(self, embeddings):
        """
        Create a lookup layer for embeddings.
        Input:
            embeddings -- embeddings of tokens, shape (|vocab|, embedding_dim). 
        Output:
            embed_layer -- a lookup layer for embeddings.
                           inputs token' ID and returns token's embedding.
        """
        embed_layer = nn.Embedding(self.vocab_size, self.embedding_dim)
        embed_layer.weight.data = torch.from_numpy(embeddings)
        embed_layer.weight.requires_grad = bool(self.args.fine_tuning)
        return embed_layer


    def forward(self, x, m):
        """
        Inputs:
            x -- input x, shape (batch_size, seq_len),
                 each element in the seq_len is of 0-|vocab| pointing to a token.
            m -- mask m, shape (batch_size, seq_len).
                 each element in the seq_len is of 0/1 selecting a token or not.
                 (Not used in this model.)
        Outputs:
            predict -- prediction score of the label, shape (batch_size, |label|),
                       each element at i is a predicted probability for label[i].
        """

        # Lookup embeddings of each token,
        # (batch_size, seq_len) -> (batch_size, seq_len, embedding_dim).
        word_embeddings = self.embed_layer(x)

        # Sum word embedding's across the sequence dimension (BoW),
        # (batch_size, seq_len, embedding_dim) -> (batch_size, embedding_dim).
        doc_embedding = word_embeddings.sum(dim=1)
        doc_embedding = (doc_embedding > 0).float()  # Binary.

        # Feed to a forward layer and get predictions,
        # (batch_size, embedding_dim) -> (batch_size,).
        predict = self.linear(doc_embedding)
        return predict, [], [], []


    def train_one_step(self, x, y, m, r, s, d):
        """
        Inputs:
            x -- input x, shape (batch_size, seq_len),
                 each element in the seq_len is of 0-|vocab| pointing to a token.
            y -- label y, shape (batch_size,),
                 only one scalar per instance 0-|label| pointing to a label.
            m -- not used in this model.
            r -- not used in this model.
            s -- not used in this model.
            d -- not used in this model.
        Outputs:
            losses -- a dict storing values of losses, only one loss in this model.
            predict -- prediction score of the label, shape (batch_size, |label|),
                       each element at i is a predicted probability for label[i].
            z -- not used in this model.
        """

        # Get prediction.
        predict, _, _, _ = self(x, m)

        # Get loss.
        loss = self.pred_loss(predict, y)

        # Backpropagate.
        loss.backward()
        self.opt.step()
        self.opt.zero_grad()

        return {"loss": loss.data}, predict, None
