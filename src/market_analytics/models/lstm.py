"""CPU LSTM training and five-horizon change forecasts."""

import io
import random
from pathlib import Path
import numpy as np
import torch
from torch import nn


def configure_cpu(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    if torch.version.cuda is not None:
        raise RuntimeError('This project requires the CPU-only torch build')


class SpreadLSTM(nn.Module):
    def __init__(self, hidden_size):
        super().__init__()
        self.recurrent = nn.LSTM(5,hidden_size,num_layers=1,batch_first=True)
        self.head = nn.Linear(hidden_size,5)

    def forward(self, x):
        output,_ = self.recurrent(x)
        return self.head(output[:,-1,:])


class EarlyStopping:
    def __init__(self, patience=20,min_delta=1e-6):
        self.patience,self.min_delta = patience,min_delta
        self.best_loss,self.best_epoch,self.wait,self.stopped = float('inf'),0,0,False

    def update(self, loss, epoch):
        if not np.isfinite(loss):
            raise ValueError('Non-finite validation loss')
        improved = loss < self.best_loss-self.min_delta
        if improved:
            self.best_loss,self.best_epoch,self.wait = float(loss),epoch,0
        else:
            self.wait += 1
        self.stopped = self.wait>=self.patience
        return improved


def _inputs(x):
    array = np.asarray(x,dtype=np.float32)
    if array.ndim!=3 or array.shape[1:]!=(20,5) or len(array)==0 or not np.isfinite(array).all():
        raise ValueError('Expected finite (N,20,5) model inputs')
    return torch.from_numpy(np.ascontiguousarray(array))


def predict_changes(model,x):
    model.eval()
    with torch.inference_mode():
        result = model(_inputs(x)).cpu().numpy()
    if not np.isfinite(result).all():
        raise ValueError('Non-finite model forecast')
    return result


def train_model(x,y,settings,*,validation=None,epochs=None):
    configure_cpu(settings['seed'])
    inputs = _inputs(x)
    targets = torch.as_tensor(np.asarray(y,dtype=np.float32))
    if targets.shape!=(len(inputs),5) or not torch.isfinite(targets).all():
        raise ValueError('Expected finite (N,5) change targets')
    model = SpreadLSTM(settings['hidden_size'])
    optimizer = torch.optim.Adam(model.parameters(),lr=settings['learning_rate'],weight_decay=0.)
    generator = torch.Generator().manual_seed(settings['seed'])
    stopping = EarlyStopping(settings['patience'],settings['min_delta'])
    if (validation is None) != (epochs is not None):
        raise ValueError('Choose validation selection or a fixed final epoch count')
    val = (_inputs(validation[0]),torch.as_tensor(validation[1],dtype=torch.float32)) if validation is not None else None
    history,best_state = [],None
    for epoch in range(1,(epochs if epochs is not None else settings['max_epochs'])+1):
        model.train()
        total = 0.
        order = torch.randperm(len(inputs),generator=generator)
        for batch in order.split(settings['batch_size']):
            optimizer.zero_grad(set_to_none=True)
            loss = nn.functional.mse_loss(model(inputs[batch]),targets[batch])
            if not torch.isfinite(loss):
                raise ValueError('Non-finite training loss')
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(),settings['gradient_clip'],error_if_nonfinite=True)
            optimizer.step()
            total += float(loss.detach())*len(batch)
        validation_mse = None
        if val is not None:
            model.eval()
            with torch.inference_mode():
                validation_mse = float(nn.functional.mse_loss(model(val[0]),val[1]))
            if stopping.update(validation_mse,epoch):
                best_state = {k:v.detach().clone() for k,v in model.state_dict().items()}
        history.append({'epoch':epoch,'training_mse':total/len(inputs),'validation_mse':validation_mse})
        if val is not None and stopping.stopped:
            break
    if val is not None:
        model.load_state_dict(best_state)
    if not all(torch.isfinite(v).all() for v in model.parameters()):
        raise ValueError('Non-finite trained weights')
    return model,history,stopping.best_epoch if val is not None else int(epochs)


def checkpoint_bytes(model):
    buffer = io.BytesIO()
    torch.save(model.state_dict(),buffer)
    return buffer.getvalue()


def save_checkpoint(model,path):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(checkpoint_bytes(model))


def load_checkpoint(path,hidden_size):
    configure_cpu(42)
    model = SpreadLSTM(hidden_size)
    model.load_state_dict(torch.load(path,map_location='cpu',weights_only=True),strict=True)
    if not all(torch.isfinite(v).all() for v in model.parameters()):
        raise ValueError('Non-finite saved weights')
    return model.eval()
