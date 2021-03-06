import gym
import yaml
import numpy as np
import random
from gym import error, utils
from gym.spaces import Discrete, Box
from gym.utils import seeding
import os

'''
calls _check_rep before and after the function to ensure it did not violate the invariants
'''
def check_rep_decorate(func):
    def func_wrapper(self,*args, **kwargs):
        # self._check_rep()
        out = func(self,*args, **kwargs)
        # self._check_rep()
        return out
    return func_wrapper

class ColorEnv(gym.Env):

    def __init__(self, path_to_config):
        # read in configuration file
        with open(path_to_config, "r") as yamlfile:
            config = yaml.safe_load(yamlfile)

            self.n = config['gym']['n'] # n is the sidelength of our square gameboard, must be greater than 1
            self.num_colors = config['gym']['num_colors'] # number of colors that the AI can choose from
            self.maximize_red = config['gym']['maximize_red'] # enables different reward scheme, 1 for every red placement, -100 for invalid layout at the end
            self.ordered_placement = config['gym']['ordered_placement'] # true results in deterministic placement order
            self.disable_checking = config['gym']['disable_checking'] # turns off board color checking at terminal step
            self.flatten = config['gym']['flatten'] # if true, flatttens the state to a 1d vector before returning

            seed = config['gym']['seed']
            if (seed != None):
                random.seed(seed)

        self.action_space = Discrete(self.num_colors)
        if self.flatten:
            self.observation_space = Box(low=0, high=self.num_colors+1, shape=(self.n * self.n * 2,), dtype=np.int32)
        else:
            self.observation_space = Box(low=0, high=self.num_colors+1, shape=(self.n, self.n, 2), dtype=np.int32)

        self._new_free_coords()

        # two n x n arrays stacked on top of each other, the first is the gameboard where 0 = no piece
        # and any other number represents the color at that location
        # the second array is the placement array, which is all zero except one 1 in the next location to put a piece in
        self.state = np.zeros((self.n,self.n,2), dtype = int)

        self.counter = 0 # the number of pieces that have been placed
        self.done = False # true if environement has reached terminal state, false otherwise

        self._first_location()

        self.state[self.current_loc[0],self.current_loc[1],1] = 1

    '''
    returns the view the agent gets of the state, which is either identical to the the internal
    state view or a flattened view depending on the self.flatten paramater set during config
    '''
    def _get_state_agent_view(self):
        if self.flatten:
            return self.state.flatten()
        else:
            return self.state

    '''
    gets the first location to place a piece on before returning the board state for the first time
    the result depends on whether the placement order is deterministic (controlled by self.ordered_placement)
    '''
    def _first_location(self):
        if self.ordered_placement:
            self.current_loc = self.free_coords.pop(0)
        else:
            # set the first location in the placement array
            self.current_loc = random.choice(tuple(self.free_coords)) # the next location to place a piece at
            self.free_coords.remove(self.current_loc)

    '''
    regenerates the self.ordered_placement collection, which is an ordered list if placement
    is deterministic and a set if placement order is non-deterministic
    '''
    def _new_free_coords(self):
        if self.ordered_placement:
            self.free_coords = []
            for i in range(self.n):
                for j in range(self.n):
                    self.free_coords.append((i,j))
        else:
            self.free_coords = set() # a set of all the remaining coordinates to put pieces in
            for i in range(self.n):
                for j in range(self.n):
                    self.free_coords.add((i,j))

    '''
    gets the number of non-zero elements in the provided array
    '''
    def _num_nonzero(self,arr):
        return len(np.transpose(np.nonzero(arr)))

    '''
    validates that the internal representation is consistent with the design invariants
    '''
    def _check_rep(self):
        assert self.n > 0, "n must be positive and non-zero"
        if self.done:
            assert len(self.free_coords) == 0, "there are still coords remaining"
            assert self._num_nonzero(self.state[:,:,0]) == self.n ** 2, "there are empty spaces"
            assert self.counter == self.n ** 2, "the counter is not correct"
        else:
            num_pieces = self._num_nonzero(self.state[:,:,0])
            assert num_pieces != self.n ** 2, "the board is filled but not marked as done"
            assert num_pieces == self.counter, "the count is off"
            assert self._num_nonzero(self.state[:,:,1]) == 1, "there none or too many current placement locations specified"


    '''
    gets a new location from the free_coords set and sets the old location to
    zero while setting the new location to one in the placement array
    '''
    @check_rep_decorate
    def _get_next_location(self):
        assert len(self.free_coords), "free_coords is empty, there are no more positions availble"

        if self.ordered_placement:
            new_loc = self.free_coords.pop(0)
        else:
            # get new location and remove it from future options
            new_loc = random.choice(tuple(self.free_coords))
            self.free_coords.remove(new_loc)

        # set old location in placement array to 0, set new location to 1
        self.state[self.current_loc[0],self.current_loc[1],1] = 0
        self.current_loc = new_loc
        self.state[self.current_loc[0],self.current_loc[1],1] = 1

    '''
    checks if the given location tuple (x,y) is inside of the n x n board and returns boolean accordingly
    '''
    @check_rep_decorate
    def _is_valid_location(location):
        return location[0] >= 0 and location[0] < self.n and location[1] >= 0 and location[1] < self.n

    '''
    assumes that the board is full of pieces, i.e. that self.counter == self.n * self.n
    checks if the board is in a legal configuration according to the self.num_colors coloring rule
    returns false if illegal board configuration, true if legal board configuration
    '''
    @check_rep_decorate
    def _check_legal_board(self):
        if self.disable_checking:
            return True

        board = self.state[:,:,0]

        # checks for all pieces (except the last column and row)
        # that the pieces below and to the right are not the same color
        for i in range(self.n - 1):
            for j in range(self.n - 1):
                if board[i, j] == board[i+1, j] or board[i, j] == board[i, j+1]:
                    return False

        #check the bottom right corner against its two neighbors
        bot_right = board[self.n - 1, self.n - 1]
        if bot_right == board[self.n - 2, self.n - 1] or bot_right == board[self.n - 1, self.n - 2]:
            return False

        return True

    '''
    takes in an agents intended action, update board state and increment coutner
    if board is full, i.e. self.counter == self.n * self.n then check if
    the board is in a legal configuration, returning a reward of 1 or 0 if not valid
    '''
    @check_rep_decorate
    def step(self, action):
        action = action + 1 # action goes from 0 to num_colors-1 so we need to add one to get the actual color

        # assert action <= self.num_colors, "this color {} is not legal".format(action)
        # assert action > 0, "this color {} is not legal".format(action)
        if (action > self.num_colors or action <= 0):
            print("Illegal action: {} attempted.".format(action))
            return [self._get_state_agent_view(), -1, self.done, {}]

        if self.done:
            print("Game is already over")
            return [self._get_state_agent_view(), 0, self.done, {}]

        self.counter += 1
        self.state[self.current_loc[0],self.current_loc[1],0] = action
        reward = 1 if self.maximize_red and action == 1 else 0

        # check if game is over
        if self.counter == self.n ** 2:
            self.done = True
            self.state[self.current_loc[0], self.current_loc[1], 1] = 0
            if self._check_legal_board():
                reward = 1
            else:
                reward = -100 if self.maximize_red else 0

            # self.render()

        else:
            self._get_next_location()

        return [self._get_state_agent_view(), reward, self.done, {}]

    '''
    resets the board to be entirely empty with a random next placement location
    '''
    @check_rep_decorate
    def reset(self):
        self._new_free_coords()

        self.state = np.zeros((self.n, self.n, 2), dtype = int)
        self.counter = 0
        self.done = 0

        self._first_location()

        return self._get_state_agent_view()

    def render(self, mode='human', close=False):
        print("Board state:")
        print(self.state[:,:,0])
        print("Placement array:")
        print(self.state[:,:,1])
        print()
