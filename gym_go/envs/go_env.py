import collections
from enum import Enum

import gym
import numpy as np

from gym_go import govars, rendering, gogame



class RewardMethod(Enum):
    """
    REAL: 0 = game is ongoing, 1 = black won, -1 = game tied or white won
    HEURISTIC: If game is ongoing, the reward is the area difference between black and white.
    Otherwise the game has ended, and if black has more area, the reward is BOARD_SIZE**2, otherwise it's -BOARD_SIZE**2
    """
    REAL = 'real'
    HEURISTIC = 'heuristic'


class GoEnv(gym.Env):
    metadata = {'render.modes': ['terminal', 'human']}
    govars = govars
    gogame = gogame
    timestep = 0

    def __init__(self, size, komi=0, reward_method='real'):
        '''
        @param reward_method: either 'heuristic' or 'real'
        heuristic: gives # black pieces - # white pieces.
        real: gives 0 for in-game move, 1 for winning, -1 for losing,
            0 for draw, all from black player's perspective
        '''
        self.timestep = 0
        self.size = size
        self.komi = komi
        self.state_ = gogame.init_state(size)
        self.history = x = collections.deque(govars.NO_TIMESTEPS*np.zeros((govars.NUM_CHNLS, size, size)), govars.NO_TIMESTEPS)

        self.reward_method = RewardMethod(reward_method)
        """ space = {'observation' : gym.spaces.Box(np.float32(0), np.float32(3),
                                                shape=(size*size*3,)),
                                'legal_moves' : gym.spaces.Box(np.int64(0),np.int64(1),
                                                shape=(gogame.action_size(self.state_)-1,), dtype=np.int64)
                                }

        self.observation_space =  gym.spaces.Dict(space)  """
        self.observation_space =gym.spaces.Box(np.float32(0), np.float32(5),
                                                shape=(size*size*3,))

        self.action_space = gym.spaces.Discrete(gogame.action_size(self.state_))
        self.done = False

    def reset(self):
        '''
        Reset state, go_board, curr_player, prev_player_passed,
        done, return state
        '''
        self.state_ = gogame.init_state(self.size)
        self.done = False
        self.timestep = 0
        print("RESET!!")

        """ observations_and_legal_moves = {'observation' : np.copy(self.state_)[:3].flatten(),
                                        'legal_moves' : 1-self.state_[govars.INVD_CHNL].flatten()
                                        }
        return observations_and_legal_moves """
        return np.copy(self.state_)[:3].flatten()

    def step(self, action):

        print("stepping")
        '''
        Assumes the correct player is making a move. Black goes first.
        return observation, reward, done, info
        '''
        try:
            assert not self.done
        except AssertionError:
            print("Valid Moves",self.valid_moves())
            print("Invalid Moves :", gogame.invalid_moves(self.state_))
            exit()
        if isinstance(action, tuple) or isinstance(action, list) or isinstance(action, np.ndarray):
            assert 0 <= action[0] < self.size
            assert 0 <= action[1] < self.size
            action = self.size * action[0] + action[1]
        elif action is None:
            action = self.size ** 2

        prev = np.copy(self.state_)
        self.state_ = gogame.next_state(self.state_, action, canonical=False)
        self.done = gogame.game_ended(self.state_)
        print("returning done as",self.done)
        self.timestep += 1
        """ observations_and_legal_moves = {'observation' : np.copy(self.state_)[:3].flatten(),
                                        'legal_moves' : 1-self.state_[govars.INVD_CHNL].flatten()
                                        }

        return observations_and_legal_moves, self.reward(), self.done, self.info() """

        return np.copy(self.state_)[:3].flatten(), self.reward(), self.done, self.info()

    def game_ended(self):
        return self.done

    def turn(self):
        return gogame.turn(self.state_)

    def prev_player_passed(self):
        return gogame.prev_player_passed(self.state_)

    def valid_moves(self):
        return gogame.valid_moves(self.state_)

    def uniform_random_action(self):
        valid_moves = self.valid_moves()
        valid_move_idcs = np.argwhere(valid_moves).flatten()
        print("valid_moves :",valid_move_idcs)
        return np.random.choice(valid_move_idcs)

    def info(self):
        """
        :return: Debugging info for the state
        """
        return {
            'turn': gogame.turn(self.state_),
            'invalid_moves': gogame.invalid_moves(self.state_),
            'prev_player_passed': gogame.prev_player_passed(self.state_),
        }

    def state(self):
        """
        :return: copy of state
        """
        return np.copy(self.state_)

    def canonical_state(self):
        """
        :return: canonical shallow copy of state
        """
        return gogame.canonical_form(self.state_)

    def children(self, canonical=False, padded=True):
        """
        :return: Same as get_children, but in canonical form
        """
        return gogame.children(self.state_, canonical, padded)

    def winning(self):
        """
        :return: Who's currently winning in BLACK's perspective, regardless if the game is over
        """
        return gogame.winning(self.state_, self.komi)

    def winner(self):
        """
        Get's the winner in BLACK's perspective
        :return:
        """

        if self.game_ended():
            return self.winning()
        else:
            return 0

    def reward(self):
        '''
        Return reward based on reward_method.
        heuristic: black total area - white total area
        real: 0 for in-game move, 1 for winning, 0 for losing,
            0.5 for draw, from black player's perspective.
            Winning and losing based on the Area rule
            Also known as Trump Taylor Scoring
        Area rule definition: https://en.wikipedia.org/wiki/Rules_of_Go#End
        '''
        if self.reward_method == RewardMethod.REAL:
            return self.winner()

        elif self.reward_method == RewardMethod.HEURISTIC:
            black_area, white_area = gogame.areas(self.state_)
            area_difference = black_area - white_area
            komi_correction = area_difference - self.komi
            if self.game_ended():
                return (1 if komi_correction > 0 else -1) * self.size ** 2
            return komi_correction
        else:
            raise Exception("Unknown Reward Method")

    def __str__(self):
        return gogame.str(self.state_)

    def close(self):
        if hasattr(self, 'window'):
            assert hasattr(self, 'pyglet')
            self.window.close()
            self.pyglet.app.exit()

    def render(self, mode='terminal'):
        if mode == 'terminal':
            print(self.__str__())
        elif mode == 'human':
            import pyglet
            from pyglet.window import mouse
            from pyglet.window import key

            screen = pyglet.canvas.get_display().get_default_screen()
            window_width = int(min(screen.width, screen.height) * 2 / 3)
            window_height = int(window_width * 1.2)
            window = pyglet.window.Window(window_width, window_height)

            self.window = window
            self.pyglet = pyglet
            self.user_action = None

            # Set Cursor
            cursor = window.get_system_mouse_cursor(window.CURSOR_CROSSHAIR)
            window.set_mouse_cursor(cursor)

            # Outlines
            lower_grid_coord = window_width * 0.075
            board_size = window_width * 0.85
            upper_grid_coord = board_size + lower_grid_coord
            delta = board_size / (self.size - 1)
            piece_r = delta / 3.3  # radius

            @window.event
            def on_draw():
                pyglet.gl.glClearColor(0.7, 0.5, 0.3, 1)
                window.clear()

                pyglet.gl.glLineWidth(3)
                batch = pyglet.graphics.Batch()

                # draw the grid and labels
                rendering.draw_grid(batch, delta, self.size, lower_grid_coord, upper_grid_coord)

                # info on top of the board
                rendering.draw_info(batch, window_width, window_height, upper_grid_coord, self.state_)

                # Inform user what they can do
                rendering.draw_command_labels(batch, window_width, window_height)

                rendering.draw_title(batch, window_width, window_height)

                batch.draw()

                # draw the pieces
                rendering.draw_pieces(batch, lower_grid_coord, delta, piece_r, self.size, self.state_)

            @window.event
            def on_mouse_press(x, y, button, modifiers):
                if button == mouse.LEFT:
                    grid_x = (x - lower_grid_coord)
                    grid_y = (y - lower_grid_coord)
                    x_coord = round(grid_x / delta)
                    y_coord = round(grid_y / delta)
                    try:
                        self.window.close()
                        pyglet.app.exit()
                        self.user_action = (x_coord, y_coord)
                    except:
                        pass

            @window.event
            def on_key_press(symbol, modifiers):
                if symbol == key.P:
                    self.window.close()
                    pyglet.app.exit()
                    self.user_action = None
                elif symbol == key.R:
                    self.reset()
                    self.window.close()
                    pyglet.app.exit()
                elif symbol == key.E:
                    self.window.close()
                    pyglet.app.exit()
                    self.user_action = -1

            pyglet.app.run()

            return self.user_action
