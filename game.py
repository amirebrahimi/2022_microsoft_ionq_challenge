from qiskit import execute, Aer, QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.providers.aer import StatevectorSimulator, QasmSimulator, UnitarySimulator
import matplotlib.pyplot as plt
from matplotlib import cm
import numpy as np
import random
import ipywidgets as widgets
import threading
import time

class Game:    
    def __init__(self):
        self.backend = StatevectorSimulator()
        self.state = QuantumCircuit(1)
        self.gates = []
        self.points = []
        self.n_theta = 16 # number of values for theta
        self.n_phi = 16 # number of values for phi
        self.covered = np.zeros((self.n_phi, self.n_theta))
        self.theta, self.phi = np.mgrid[0:1*np.pi:self.n_theta*1j, 0:2.0*np.pi:self.n_phi*1j]
        self.thread = None
        self.add_gate('i') # start in |0> state

    @staticmethod
    def _statevector_to_cartesian(sv):
        # from https://en.wikipedia.org/wiki/Bloch_sphere#Plotting_pure_two-spinor_states_through_stereographic_projection
        u = complex(0)
        if np.abs(sv[0]) > 0:
            u = sv[1] / sv[0]
            ux = u.real
            uy = u.imag
            x = 2 * ux / (1 + ux**2 + uy**2)
            y = 2 * uy / (1 + ux**2 + uy**2)
            z = (1 - ux**2 - uy**2) / (1 + ux**2 + uy**2)
        else:
            x = 0
            y = 0
            z = -1
        return [x, y, z]
    
    @staticmethod
    def _fibonacci_sphere(samples=1000):
        points = []
        phi = np.pi * (3. - np.sqrt(5.))  # golden angle in radians

        for i in range(samples):
            y = 1 - (i / float(samples - 1)) * 2  # y goes from 1 to -1
            radius = np.sqrt(1 - y * y)  # radius at y

            theta = phi * i  # golden angle increment

            x = np.cos(theta) * radius
            z = np.sin(theta) * radius

            points.append((x, y, z))

        return points
#     @staticmethod
#     def _fibonacci_sphere(num_points: int):
#         ga = (3 - np.sqrt(5)) * np.pi # golden angle                                                                             

#         # Create a list of golden angle increments along tha range of number of points                                           
#         theta = ga * np.arange(num_points)

#         # Z is a split into a range of -1 to 1 in order to create a unit circle                                                  
#         z = np.linspace(1/num_points-1, 1-1/num_points, num_points)

#         # a list of the radii at each height step of the unit circle                                                             
#         radius = np.sqrt(1 - z * z)

#         # Determine where xy fall on the sphere, given the azimuthal and polar angles                                            
#         y = radius * np.sin(theta)
#         x = radius * np.cos(theta)
        
#         return list(zip(x, y, z))
    
    @staticmethod
    def _get_magic_state_result(use_real_data=True):
        if use_real_data:
            # this data comes from running a magic state distillation circuit on IonQ hardware
            probabilities = {'00000': 0.0272216796875, '00001': 0.0286865234375, '00010': 0.025390625, '00011': 0.04638671875, '00100': 0.009521484375, '00101': 0.0272216796875, '00110': 0.0111083984375, '00111': 0.0380859375, '01000': 0.0423583984375, '01001': 0.01513671875, '01010': 0.0386962890625, '01011': 0.01171875, '01100': 0.0220947265625, '01101': 0.010498046875, '01110': 0.029541015625, '01111': 0.02783203125, '10000': 0.032958984375, '10001': 0.1297607421875, '10010': 0.0389404296875, '10011': 0.021240234375, '10100': 0.0130615234375, '10101': 0.04541015625, '10110': 0.0205078125, '10111': 0.0306396484375, '11000': 0.053466796875, '11001': 0.017822265625, '11010': 0.0283203125, '11011': 0.0098876953125, '11100': 0.022705078125, '11101': 0.017333984375, '11110': 0.0477294921875, '11111': 0.0587158203125}
            
            result = random.choices(list(probabilities.keys()), weights=probabilities.values())[0]
        else:
            bs = random.getrandbits(5)
            result = ''.join('{:05b}'.format(bs))
        return result
    
    def next_round(self):
        self.gates = []
        for _ in range(5):
            bs = Game._get_magic_state_result()
            if bs.endswith('0000'):
                self.gates.append('t')
            else:
                cliffords = ['h', 'x', 'y', 'z', 's', 'sdg']
                self.gates.append(cliffords[random.randrange(len(cliffords))])        
    
    def add_gate(self, gate):
        op = getattr(self.state, gate)
        op(0)
        results = self.backend.run(self.state).result()
        psi = results.get_statevector()
        point = Game._statevector_to_cartesian(psi)
        self.points.append(point)
        
        r = 1
        theta, phi = self.theta, self.phi
        
        # update what areas are covered
        min_norm = 1
        for j in phi[0,:]:
            for i in theta[:,0]:
                _x = r*np.sin(i)*np.cos(j)
                _y = r*np.sin(i)*np.sin(j)
                _z = r*np.cos(i)
                diff = [_x, _y, _z] - np.array(point)
                min_norm = min(min_norm, np.linalg.norm(diff))

        for pindex, j in enumerate(phi[0,:]):
            for tindex, i in enumerate(theta[:,0]):
                _x = r*np.sin(i)*np.cos(j)
                _y = r*np.sin(i)*np.sin(j)
                _z = r*np.cos(i)
                diff = (_x, _y, _z) - np.array(point)
                if np.linalg.norm(diff) <= min_norm:
#                 print(pindex, tindex, (_x, _y, _z), np.linalg.norm(diff), min_norm)
                    self.covered[pindex, tindex] = 1 - self.covered[pindex, tindex]

    def draw(self):
        # from https://stackoverflow.com/questions/41105754/heat-map-half-sphere-plot
        r = 1        #radius of sphere

        theta, phi = self.theta, self.phi

        x = r*np.sin(theta)*np.cos(phi)
        y = r*np.sin(theta)*np.sin(phi)
        z = r*np.cos(theta)

        # mimic the input array
        # array columns phi, theta, value
        # first n_theta entries: phi=0, second n_theta entries: phi=0.0315..
        inp = []
        for pindex, j in enumerate(phi[0,:]):
            for tindex, i in enumerate(theta[:,0]):
                val = 1 - self.covered[pindex, tindex] * 0.75
                inp.append([j, i, val])
        inp = np.array(inp)
        
        #reshape the input array to the shape of the x,y,z arrays. 
        c = inp[:,2].reshape((self.n_phi,self.n_theta)).T
#         c[-2:-1,:] = 0.25
#         print(cm.hot(c))

        #Set colours and render
        fig = plt.figure(figsize=(8, 8))
        ax = fig.add_subplot(111, projection='3d')
        # use facecolors argument, provide array of same shape as z
        #  cm.<cmapname>() allows to get rgba color from array.
        #  array must be normalized between 0 and 1
#         ax.plot_surface(
#             x,y,z, rstride=1, cstride=1, facecolors=cm.hot(c/c.max()), alpha=0.6, linewidth=1)         
        ax.plot_surface(
            x,y,z,  rstride=1, cstride=1, facecolors=cm.hot(c), alpha=0.6, linewidth=1) 
        ax.view_init(25, 45)
#         for angle in range(0, 360):
#             ax.view_init(30, angle)
#             plt.draw()
#             plt.pause(.001)
        # ax.set_xlim([-2.2,2.2])
        # ax.set_ylim([-2.2,2.2])
        # ax.set_zlim([0,4.4])
        plt.quiver(*np.zeros(3), *self.points[-1], length=1, color=['g'], normalize=True)
        plt.close(fig)
        return fig

    def play(self):
        buttons = []
        
        def update_buttons(buttons):
            for i, b in enumerate(buttons):
                b.description = self.gates[i]
                b.disabled = False
                if b.description == 't':
                    b.icon = 'check'
                else:
                    b.icon = ''
        
        class TimerThread(threading.Thread):
            # from https://stackoverflow.com/questions/323972/is-there-any-way-to-kill-a-thread
            """Thread class with a stop() method. The thread itself has to check
            regularly for the stopped() condition."""

            def __init__(self, game=None, *args, **kwargs):
                super(TimerThread, self).__init__(target=self.update_timer, *args, **kwargs)
                self._stop_event = threading.Event()
                self.game = game

            def stop(self):
                self._stop_event.set()

            def stopped(self):
                return self._stop_event.is_set()            

            def update_timer(self, timer, countdown):
                max_time = 60 * 2
                time_left = max_time
                round_time = 5
                delta = 0.2
                total = int(round_time/delta)
                while True:
                    for i in range(total):
                        if self.stopped():
                            return
                        time.sleep(delta)
                        timer.value = (total - float(i+1))/total
                        time_left -= delta
                        if time_left < 0:
                            countdown.value = f"Game Over! Final score: {np.sum(self.game.covered)}"
                            timer.value = 0
                            for b in buttons:
                                b.description = "😎"
                                b.icon = ''
                                b.disabled = True
                            return
                        mins = int(time_left / 60)
                        secs = int(time_left) % 60
                        countdown.value = 'Game time left: {minute:02}:{second:02}'.format(minute=mins,second=secs)
                    self.game.next_round()
                    update_buttons(buttons)                    
        
        def change_icon(btn):
            self.add_gate(btn.description)
            btn.description = '?'
            btn.icon = ''
            btn.disabled = True
            status = [b.disabled for b in buttons]
            if all(status):
                self.next_round()
                update_buttons(buttons)
            bloch_sphere.update()

        # start the game
        self.next_round()
            
        for g in self.gates:
            button = widgets.Button(
                description=g,
                disabled=False,
        #         button_style='', # 'success', 'info', 'warning', 'danger' or ''
        #         icon='check' # (FontAwesome names without the `fa-` prefix)
            )
            button.on_click(change_icon)
            buttons.append(button)
            
        timer = widgets.FloatProgress(value=0.0, min=0.0, max=1.0)
        countdown = widgets.Label(value="")
            
        if self.thread is not None:
            self.thread.stop()
            self.thread.join()
        self.thread = TimerThread(game=self, args=(timer,countdown))
        self.thread.start()
    
        bloch_sphere = widgets.interactive(lambda: display(self.draw()))
        return widgets.VBox([countdown, timer, widgets.HBox(buttons), bloch_sphere])