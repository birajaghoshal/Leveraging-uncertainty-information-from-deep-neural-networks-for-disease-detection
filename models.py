from collections import OrderedDict
import warnings
import cPickle as pickle
import numpy as np

import theano
import theano.tensor as T
import lasagne

try:
    from lasagne.layers.dnn import Conv2DDNNLayer as ConvLayer
    from lasagne.layers.dnn import MaxPool2DDNNLayer as MaxPool2DLayer
except ImportError:
    warnings.warn("cuDNN not available, using theano's conv2d instead.")
    from lasagne.layers import Conv2DLayer as ConvLayer
    from lasagne.layers import MaxPool2DLayer

from lasagne.layers import InputLayer
from lasagne.layers import ConcatLayer
from lasagne.layers import DenseLayer
from lasagne.layers import DropoutLayer
from lasagne.layers import FeaturePoolLayer
from lasagne.layers import NonlinearityLayer
from lasagne.layers import ReshapeLayer
from lasagne.layers import set_all_param_values

from lasagne.nonlinearities import softmax, LeakyRectify


class Model(object):
    """Encapsulate Lasagne model

    Note on concept
    ===============

    Variables are dicts which contain symbolic theano variables or lasagne
    layers. Method arguments are typically actual data such as arrays.

    """

    def __init__(self, net=OrderedDict()):

        self.net = net
        self.inputs = OrderedDict([('X', T.tensor4('X'))])
        self.targets = OrderedDict([('y', T.ivector('y'))])

        self._predict = None
        self._predict_stoch = None

    def predict(self, *inputs):
        """Forward pass"""
        if self._predict is None:
            self._predict = theano.function(self.inputs.values(),
                lasagne.layers.get_output(self.net.values()[-1],
                                          deterministic=True))
        return self._predict(*inputs)

    def mc_samples(self, *inputs, **kwargs):
        """Stochastic forward passes to generate T MC samples"""
        T = kwargs.pop('T', 100)
        if kwargs:
            raise TypeError('Unexpected **kwargs: %r' % kwargs)
        if self._predict_stoch is None:
            self._predict_stoch = theano.function(self.inputs.values(),
                lasagne.layers.get_output(self.net.values()[-1],
                                          deterministic=False))
        n_samples = len(inputs[0])
        n_out = self.net.values()[-1].output_shape[1]
        mc_samples = np.zeros((n_samples, n_out, T))
        for t in range(T):
            mc_samples[:, :, t] = self._predict_stoch(*inputs)
        return mc_samples

    def get_output_layer(self):
        return self.net.values()[-1]


class JFnet(Model):

    ORIGINAL_WEIGHTS = 'models/jeffrey_df/2015_07_17_123003_PARAMSDUMP.pkl'

    def __init__(self, width=512, height=512):
        network = JFnet.build_model(width=width, height=height,
                                    filename=JFnet.ORIGINAL_WEIGHTS)
        super(JFnet, self).__init__(net=network)
        self.inputs['X'] = self.net['0'].input_var
        self.inputs['img_dim'] = self.net['22'].input_var

    @staticmethod
    def build_model(width=512, height=512, filename=None,
                    n_classes=5, batch_size=None, p_conv=0.0):
        """Setup network structure for the original formulation of JeffreyDF's
           network and optionally load pretrained weights

        Parameters
        ----------
        width : Optional[int]
            image width
        height : Optional[int]
            image height
        filename : Optional[str]
            if filename is not None, weights are loaded from filename
        n_classes : Optional[int]
            default 5 for transfer learning on Kaggle DR data
        batch_size : should only be set if all batches have the same size!
        p_conv: dropout applied to conv. layers, by default turned off (0.0)

        Returns
        -------
        dict
            one lasagne layer per key

        Notes
        -----
            Reference: Jeffrey De Fauw, 2015:
            http://jeffreydf.github.io/diabetic-retinopathy-detection/

            Download pretrained weights from:
            https://github.com/JeffreyDF/kaggle_diabetic_retinopathy/blob/
            master/dumps/2015_07_17_123003_PARAMSDUMP.pkl

           original net has leaky rectifier units

        """

        net = OrderedDict()

        net['0'] = InputLayer((batch_size, 3, width, height), name='images')
        net['1'] = ConvLayer(net['0'], 32, 7, stride=(2, 2), pad='same',
                             untie_biases=True,
                             nonlinearity=LeakyRectify(leakiness=0.5),
                             W=lasagne.init.Orthogonal(1.0),
                             b=lasagne.init.Constant(0.1))
        net['1d'] = DropoutLayer(net['1'], p=p_conv)
        net['2'] = MaxPool2DLayer(net['1d'], 3, stride=(2, 2))
        net['3'] = ConvLayer(net['2'], 32, 3, stride=(1, 1), pad='same',
                             untie_biases=True,
                             nonlinearity=LeakyRectify(leakiness=0.5),
                             W=lasagne.init.Orthogonal(1.0),
                             b=lasagne.init.Constant(0.1))
        net['3d'] = DropoutLayer(net['3'], p=p_conv)
        net['4'] = ConvLayer(net['3d'], 32, 3, stride=(1, 1), pad='same',
                             untie_biases=True,
                             nonlinearity=LeakyRectify(leakiness=0.5),
                             W=lasagne.init.Orthogonal(1.0),
                             b=lasagne.init.Constant(0.1))
        net['4d'] = DropoutLayer(net['4'], p=p_conv)
        net['5'] = MaxPool2DLayer(net['4d'], 3, stride=(2, 2))
        net['6'] = ConvLayer(net['5'], 64, 3, stride=(1, 1), pad='same',
                             untie_biases=True,
                             nonlinearity=LeakyRectify(leakiness=0.5),
                             W=lasagne.init.Orthogonal(1.0),
                             b=lasagne.init.Constant(0.1))
        net['6d'] = DropoutLayer(net['6'], p=p_conv)
        net['7'] = ConvLayer(net['6d'], 64, 3, stride=(1, 1), pad='same',
                             untie_biases=True,
                             nonlinearity=LeakyRectify(leakiness=0.5),
                             W=lasagne.init.Orthogonal(1.0),
                             b=lasagne.init.Constant(0.1))
        net['7d'] = DropoutLayer(net['7'], p=p_conv)
        net['8'] = MaxPool2DLayer(net['7d'], 3, stride=(2, 2))
        net['9'] = ConvLayer(net['8'], 128, 3, stride=(1, 1), pad='same',
                             untie_biases=True,
                             nonlinearity=LeakyRectify(leakiness=0.5),
                             W=lasagne.init.Orthogonal(1.0),
                             b=lasagne.init.Constant(0.1))
        net['9d'] = DropoutLayer(net['9'], p=p_conv)
        net['10'] = ConvLayer(net['9d'], 128, 3, stride=(1, 1), pad='same',
                              untie_biases=True,
                              nonlinearity=LeakyRectify(leakiness=0.5),
                              W=lasagne.init.Orthogonal(1.0),
                              b=lasagne.init.Constant(0.1))
        net['10d'] = DropoutLayer(net['10'], p=p_conv)
        net['11'] = ConvLayer(net['10d'], 128, 3, stride=(1, 1), pad='same',
                              untie_biases=True,
                              nonlinearity=LeakyRectify(leakiness=0.5),
                              W=lasagne.init.Orthogonal(1.0),
                              b=lasagne.init.Constant(0.1))
        net['11d'] = DropoutLayer(net['11'], p=p_conv)
        net['12'] = ConvLayer(net['11d'], 128, 3, stride=(1, 1), pad='same',
                              untie_biases=True,
                              nonlinearity=LeakyRectify(leakiness=0.5),
                              W=lasagne.init.Orthogonal(1.0),
                              b=lasagne.init.Constant(0.1))
        net['12d'] = DropoutLayer(net['12'], p=p_conv)
        net['13'] = MaxPool2DLayer(net['12d'], 3, stride=(2, 2))
        net['14'] = ConvLayer(net['13'], 256, 3, stride=(1, 1), pad='same',
                              untie_biases=True,
                              nonlinearity=LeakyRectify(leakiness=0.5),
                              W=lasagne.init.Orthogonal(1.0),
                              b=lasagne.init.Constant(0.1))
        net['14d'] = DropoutLayer(net['14'], p=p_conv)
        net['15'] = ConvLayer(net['14d'], 256, 3, stride=(1, 1), pad='same',
                              untie_biases=True,
                              nonlinearity=LeakyRectify(leakiness=0.5),
                              W=lasagne.init.Orthogonal(1.0),
                              b=lasagne.init.Constant(0.1))
        net['15d'] = DropoutLayer(net['15'], p=p_conv)
        net['16'] = ConvLayer(net['15'], 256, 3, stride=(1, 1), pad='same',
                              untie_biases=True,
                              nonlinearity=LeakyRectify(leakiness=0.5),
                              W=lasagne.init.Orthogonal(1.0),
                              b=lasagne.init.Constant(0.1))
        net['16d'] = DropoutLayer(net['16'], p=p_conv)
        net['17'] = ConvLayer(net['16d'], 256, 3, stride=(1, 1), pad='same',
                              untie_biases=True,
                              nonlinearity=LeakyRectify(leakiness=0.5),
                              W=lasagne.init.Orthogonal(1.0),
                              b=lasagne.init.Constant(0.1))
        net['17d'] = DropoutLayer(net['17'], p=p_conv)
        net['18'] = MaxPool2DLayer(net['17d'], 3, stride=(2, 2),
                                   name='coarse_last_pool')
        net['19'] = DropoutLayer(net['18'], p=0.5)
        net['20'] = DenseLayer(net['19'], num_units=1024, nonlinearity=None,
                               W=lasagne.init.Orthogonal(1.0),
                               b=lasagne.init.Constant(0.1),
                               name='first_fc_0')
        net['21'] = FeaturePoolLayer(net['20'], 2)
        net['22'] = InputLayer((batch_size, 2), name='imgdim')
        net['23'] = ConcatLayer([net['21'], net['22']])
        # Combine representations of both eyes
        net['24'] = ReshapeLayer(net['23'],
                                 (-1, net['23'].output_shape[1] * 2))
        net['25'] = DropoutLayer(net['24'], p=0.5)
        net['26'] = DenseLayer(net['25'], num_units=1024, nonlinearity=None,
                               W=lasagne.init.Orthogonal(1.0),
                               b=lasagne.init.Constant(0.1),
                               name='combine_repr_fc')
        net['27'] = FeaturePoolLayer(net['26'], 2)
        net['28'] = DropoutLayer(net['27'], p=0.5)
        net['29'] = DenseLayer(net['28'],
                               num_units=n_classes * 2,
                               nonlinearity=None,
                               W=lasagne.init.Orthogonal(1.0),
                               b=lasagne.init.Constant(0.1))
        # Reshape back to the number of desired classes
        net['30'] = ReshapeLayer(net['29'], (-1, n_classes))
        net['31'] = NonlinearityLayer(net['30'], nonlinearity=softmax)

        if filename is not None:
            with open(filename, 'r') as f:
                weights = pickle.load(f)
            set_all_param_values(net['31'], weights)

        return net

    @staticmethod
    def get_img_dim(width, height):
        """Second input to JFnet consumes image dimensions

        division by 700 according to https://github.com/JeffreyDF/
        kaggle_diabetic_retinopathy/blob/
        43e7f51d5f3b2e240516678894409332bb3767a8/generators.py::lines 41-42
        """
        return np.vstack((width, height)).T / 700.


class BCNN(Model):
    """Bayesian convolutional neural network (if p != 0 and on at test time)"""

    def __init__(self, p_conv=0.2, last_layer='13', weights=None,
                 n_classes=2):
        network = JFnet.build_model(width=512, height=512,
                                    filename=JFnet.ORIGINAL_WEIGHTS,
                                    p_conv=p_conv)
        # remove unused layers
        while not network.keys()[-1] == last_layer:
            network.popitem(last=True)
        # add new layers
        mean_pooled = lasagne.layers.GlobalPoolLayer(network[last_layer],
                                                     pool_function=T.mean)
        max_pooled = lasagne.layers.GlobalPoolLayer(network[last_layer],
                                                    pool_function=T.max)
        network['global_pool'] = lasagne.layers.ConcatLayer([mean_pooled,
                                                             max_pooled],
                                                            axis=1)
        network['softmax_input'] = DenseLayer(network['global_pool'],
                                              num_units=n_classes,
                                              nonlinearity=None)
        network['logreg'] = NonlinearityLayer(network['softmax_input'],
                                              nonlinearity=softmax)

        if weights is not None:
            load_weights(network['logreg'], weights)

        super(BCNN, self).__init__(net=network)
        self.inputs['X'] = self.net['0'].input_var


def load_weights(layer, filename):
    """
    Load network weights from either a pickle or a numpy file and set
    the parameters of all layers below layer (including the layer itself)
    to the given values.

    Parameters
    ----------
    layer : Layer
        The :class:`Layer` instance for which to set all parameter values
    filename : str with ending .pkl or .npz

    """

    if filename.endswith('.npz'):
        with np.load(filename) as f:
            param_values = [f['arr_%d' % i] for i in range(len(f.files))]
        set_all_param_values(layer, param_values)
        return

    if filename.endswith('.pkl'):
        with open(filename) as handle:
            model = pickle.load(handle)
        set_all_param_values(layer, model['param values'])
        return

    raise NotImplementedError('Format of {filename} not known'.format(
        filename=filename))


def save_weights(layer, filename):
    """
    Save network weights of all layers below layer (including the layer
    itself).

    Parameters
    ----------
    layer : Layer or list
        The :class:`Layer` instance for which to gather all parameter values,
        or a list of :class:`Layer` instances.
    filename : str with ending .npz

    """

    if filename.endswith('.npz'):
        np.savez_compressed(filename,
                            *lasagne.layers.get_all_param_values(layer))
        return

    raise NotImplementedError('Format indicated by ending of {filename} not'
                              'implemented'.format(filename=filename))


def load_model(filename):
    """Load model with weights from pickle file"""
    with open(filename, 'rb') as h:
        return pickle.load(h)


def save_model(model, filename):
    """Dump model together with weights to pickle file"""
    with open(filename, 'wb') as h:
        pickle.dump(model, h)


def weights2pickle(name='bcnn1', output_layer='logreg'):
    """Convert architecture with weights and dump to pickle file

    Parameters
    ----------
    name : str
        Identifier for one of the models used in
        http://biorxiv.org/content/early/2016/10/28/084210.

        either of: 'bcnn1', 'bcnn2'

    output_layer: str
        Ablate layers after this layer. E.g. for extracting
        penultimate layer features set output_layer='global_pool'

    """

    assert name in ['bcnn1', 'bcnn2'], 'Model name is invalid.'

    if 'bcnn1' in name:
        weights = 'models/weights_bcnn1_392bea6.npz'
        outfile = 'bcnn1_392bea6_' + output_layer + '.pkl'
    elif 'bcnn2' in name:
        weights = 'models/weights_bcnn2_b69aadd.npz'
        outfile = 'bcnn2_b69aadd_' + output_layer + '.pkl'

    model = BCNN(p_conv=0.2, last_layer='17', weights=weights)

    assert output_layer in model.net.keys(), \
        'Invalid output_layer %s' % output_layer

    while not model.net.keys()[-1] == output_layer:
        model.net.popitem(last=True)

    assert model.net.keys()[-1] == output_layer

    save_model(model, outfile)
    print('Saved model to %s' % outfile)
