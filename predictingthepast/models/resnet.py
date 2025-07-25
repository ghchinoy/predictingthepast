# Copyright 2024 The Flax Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Flax implementation of ResNet V1.5."""

from collections.abc import Callable, Sequence
import functools
from typing import Any

from flax import linen as nn
import jax
import jax.numpy as jnp

ModuleDef = Any


class ResNetBlock(nn.Module):
  """ResNet block."""

  filters: int
  conv: ModuleDef
  norm: ModuleDef
  act: Callable[..., Any]
  strides: tuple[int, int] = (1, 1)

  @nn.compact
  def __call__(
      self,
      x,
  ):
    residual = x
    y = self.conv(self.filters, (3, 3), self.strides)(x)
    y = self.norm()(y)
    y = self.act(y)
    y = self.conv(self.filters, (3, 3))(y)
    y = self.norm(scale_init=nn.initializers.zeros_init())(y)

    if residual.shape != y.shape:
      residual = self.conv(
          self.filters, (1, 1), self.strides, name='conv_proj'
      )(residual)
      residual = self.norm(name='norm_proj')(residual)

    return self.act(residual + y)


class BottleneckResNetBlock(nn.Module):
  """Bottleneck ResNet block."""

  filters: int
  conv: ModuleDef
  norm: ModuleDef
  act: Callable[..., Any]
  strides: tuple[int, int] = (1, 1)

  @nn.compact
  def __call__(self, x):
    residual = x
    y = self.conv(self.filters, (1, 1))(x)
    y = self.norm()(y)
    y = self.act(y)
    y = self.conv(self.filters, (3, 3), self.strides)(y)
    y = self.norm()(y)
    y = self.act(y)
    y = self.conv(self.filters * 4, (1, 1))(y)
    y = self.norm(scale_init=nn.initializers.zeros_init())(y)

    if residual.shape != y.shape:
      residual = self.conv(
          self.filters * 4, (1, 1), self.strides, name='conv_proj'
      )(residual)
      residual = self.norm(name='norm_proj')(residual)

    return self.act(residual + y)


class ResNet(nn.Module):
  """ResNetV1.5."""

  stage_sizes: Sequence[int]
  block_cls: ModuleDef
  num_classes: int
  num_filters: int = 64
  dtype: Any = jnp.float32
  act: Callable[..., Any] = nn.gelu
  conv: ModuleDef = nn.Conv

  @nn.compact
  def __call__(self, x, train: bool = True, stop_gradient: bool = False):
    conv = functools.partial(self.conv, use_bias=False, dtype=self.dtype)
    norm = nn.LayerNorm

    x = conv(
        self.num_filters,
        (7, 7),
        (2, 2),
        padding=[(3, 3), (3, 3)],
        name='conv_init',
    )(x)
    x = norm(name='bn_init')(x)
    x = self.act(x)
    x = nn.max_pool(x, (3, 3), strides=(2, 2), padding='SAME')
    for i, block_size in enumerate(self.stage_sizes):
      for j in range(block_size):
        strides = (2, 2) if i > 0 and j == 0 else (1, 1)
        x = self.block_cls(
            self.num_filters * 2**i,
            strides=strides,
            conv=conv,
            norm=norm,
            act=self.act,
        )(x)
    x = jnp.mean(x, axis=(1, 2))
    if stop_gradient:
      x = jax.lax.stop_gradient(x)
    x = nn.Dense(self.num_classes, dtype=self.dtype)(x)
    x = jnp.asarray(x, self.dtype)
    return x


ResNet5 = functools.partial(
    ResNet, stage_sizes=[1], block_cls=BottleneckResNetBlock
)
ResNet8 = functools.partial(
    ResNet, stage_sizes=[1, 1], block_cls=BottleneckResNetBlock
)
ResNet18 = functools.partial(
    ResNet, stage_sizes=[2, 2, 2, 2], block_cls=ResNetBlock
)
ResNet34 = functools.partial(
    ResNet, stage_sizes=[3, 4, 6, 3], block_cls=ResNetBlock
)
ResNet50 = functools.partial(
    ResNet, stage_sizes=[3, 4, 6, 3], block_cls=BottleneckResNetBlock
)
ResNet101 = functools.partial(
    ResNet, stage_sizes=[3, 4, 23, 3], block_cls=BottleneckResNetBlock
)
ResNet152 = functools.partial(
    ResNet, stage_sizes=[3, 8, 36, 3], block_cls=BottleneckResNetBlock
)
ResNet200 = functools.partial(
    ResNet, stage_sizes=[3, 24, 36, 3], block_cls=BottleneckResNetBlock
)
