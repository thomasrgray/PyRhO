
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl # For plotStates
from pyrho.utilities import plotLight, calcV1
from scipy.signal import * #for argrelextrema
from scipy.integrate import odeint
import warnings
import itertools

from pyrho.parameters import *
#print(vars()['verbose'])
from pyrho.config import * #verbose, addTitles, saveFigFormat, fDir # For plotStates()
from pyrho import config
#from __init__ import verbose
from collections import OrderedDict


###### Model class definitions ######


class RhodopsinModel(PyRhOobject):
    """Common base class for all models"""
    
    phi = 0.0  # Instantaneous Light flux [photons * mm^-2 * s^-1]
    
    def __init__(self, params=None, rhoType=rhoType): #'Rhodopsin'): 
        
        if params is None:
            params = modelParams[str(self.nStates)]
        self.rhoType = rhoType # E.g. 'ChR2' or 'ArchT'
    
        self.setParams(params)
        
        # Ensure v1 is scaled correctly so that f(V=-70) = 1
        v1 = calcV1(self.E, self.v0)
        if not np.isclose(self.v1, v1, rtol=1e-3, atol=1e-5):
            warnings.warn("Correcting v1 scaling: {} <-- {}".format(self.v1, v1))
            self.v1 = v1
        
        self.initStates(phi=self.phi_0, s0=self.s_0) # phi
        #self.transRates = {r: getattr(self, r) for r in itertools.chain(self.photoRates, self.constRates)}
        
        if verbose > 1:
            print("PyRhO {}-state {} model initialised!".format(self.nStates, self.rhoType))
        
        if verbose > 2: 
            self.printParams()
        
    def __str__(self):
        #return "{} {}-state model (phi={:.3g})".format(self.rhoType, self.nStates, self.phi) # Display transition rates?
        return "{}-state {}".format(stateLabs[self.nStates], self.rhoType)   #self.__name__+
    
    def __repr__(self):
        return "<PyRhO {}-state Model object>".format(self.nStates)
    
    def __call__(self):
        """When a rhodopsin is called, return its internal state at that instant"""
        return self.calcI(self.V, self.states[-1,:])
    
    def storeStates(self, soln, t): #,pulseInds):
        self.states = np.vstack((self.states, soln)) #np.append(self.states, soln, axis=0)
        self.t = np.hstack((self.t, t)) #np.append(self.t, t, axis=1)
        #self.pulseInd = np.append(self.pulseInd, pulseInds, axis=0)
    
    def getStates(self):
        """Returns states, t"""
        return self.states, self.t
        
    def getRates(self):
        """Returns an ordered dictionary of all transition rates"""
        #return {r: getattr(self, r) for r in itertools.chain(self.photoRates, self.constRates)}
        return OrderedDict([(r, getattr(self, r)) for r in itertools.chain(self.photoRates, self.constRates)])
    
    def reportState(self):
        self.dispRates()
    
    def initStates(self, phi, s0=None):
        """Clear state arrays and set transition rates"""
        if s0 is None:
            s0 = self.s_0
        assert(len(s0)==self.nStates)
        self.states = np.vstack((np.empty([0,self.nStates]), s0)) #np.empty([0,self.nStates])
        self.t = [0] #[]
        self.pulseInd = np.empty([0,2],dtype=int) # Light on and off indexes for each pulse
        self.setLight(phi)
        #if s0 is not None: # Override default initial conditions
        #    self.s_0 = s0
    
    
    # Implement this universal function
    def calcI(self, V, states=None):#, gam=None, E=None, g=None): # Change to (V, psi)?
        """Takes Voltage [mV] and state variables O1 and O2 to calculate current [nA]
        By convention, positive ions entering the cell --> negative current (e.g. Na^+ influx). 
        Conversely, Positive ions leaving (or negative ions entering) the cell --> positive current (e.g. Cl^- in or K^+ out). """
        #if g is None:
        #g0 = self.g0
        if states is None:
            states = self.states
        #O1 = states[:,2] # O1
        #O2 = states[:,3] # O2
        #if gam is None:
        #gam = self.gam
        #if E is None:
        #E = self.E
        
        #fphi = self.calcfphi() #psi = O1 + (gam * O2) # Dimensionless
        #fv = self.calcfv()
        
        g_RhO = self.g0 * self.calcfphi(states) * self.calcfV(V) #* fV # self.gbar * self.A # Conductance (pS * um^-2)
        I_RhO = g_RhO * (V - self.E) # Photocurrent: (pS * mV)
        return I_RhO * (1e-6) # 10^-12 * 10^-3 * 10^-6 (nA)
    
    def calcfV(self, V): 
        """Method to calculate the voltage-dependent conductance scaling factor, f(v)"""
        if self.v0 == 0:    ############################################################### Finish this! Generalise!!!
            raise ZeroDivisionError("f(V) undefined for v0 = 0")
        try:
            fV = (self.v1/(V-self.E))*(1-np.exp(-(V-self.E)/self.v0)) # Dimensionless
        except ZeroDivisionError:
            if np.isscalar(V):
                if np.isclose(V, self.E): #(V == self.E):
                    fV = self.v1/self.v0
            else: #type(fV) in (tuple, list, array)
                #fV[np.isnan(fV)] = self.v1/self.v0 # Fix the error when dividing by zero
                fV[np.isclose(V-self.E, np.zeros_like(V))] = self.v1/self.v0 
        #else: 
        #    fV=1 ### Extend to vector
        return fV
    
    def calcfT(self, T):
        raise NotImplementedError
    
    def calcfpH(self, T):
        raise NotImplementedError
    
    def calcSoln(self, t, s0=None):
        if s0 is None:
            s0 = self.s_0
        return odeint(self.solveStates, s0, t, args=(None,), Dfun=self.jacobian)
    
    def plotActivation(self, actFunc, label=None, phis=np.logspace(12, 21, 1001), ax=None):
        if ax == None:
            ax = plt.gca()
        else:
            plt.sca(ax)
        
        if label is not None:
            ax.plot(phis, actFunc(phis), label=label)
            ax.legend()
        else:
            ax.plot(phis, actFunc(phis))
        ax.set_xscale('log')
        ax.set_xlabel('$\phi \ \mathrm{[photons \cdot mm^{-2} \cdot s^{-1}]}$')
        ax.set_ylabel('$\mathrm{Transition\ rate \ [ms^{-1}]}$')

        return
        
    def plotRates(self, phis=np.logspace(12, 21, 1001), logscale='both'):
        """Plot all activation rates""" #photo-sensitive
        #rfig = plt.figure()
        rFig, axR = plt.subplots()

        for r, l in zip(self.photoFuncs, self.photoLabels):
            #self.plotActivation(getattr(self, r), label=l, phis=phis, ax=axR)
            axR.plot(phis, getattr(self, r)(phis), label=l)
            #for phi in phis:
            #    self.setLight(phi)
            #    axR.plot()
        
        for r, l in zip(self.constRates, self.constLabels):
            #axR.axhline(y=r, label=l)
            axR.plot(phis, np.ones(len(phis)) * self.__dict__[r], label=l, ls='--')
        
        if logscale == 'both' or logscale == 'x':
            axR.set_xscale('log')
        if logscale == 'both' or logscale == 'y':
            axR.set_yscale('log')
        
        axR.set_xlabel('$\phi \ \mathrm{[photons \cdot mm^{-2} \cdot s^{-1}]}$')
        axR.set_ylabel('$\mathrm{Transition\ rate \ [ms^{-1}]}$')
        axR.legend(loc='best')
        
        # Tick locators take too long with log scales
        #axR.get_xaxis().set_minor_locator(mpl.ticker.AutoMinorLocator())
        #axR.get_yaxis().set_minor_locator(mpl.ticker.AutoMinorLocator())
        axR.grid(b=True, which='minor', axis='both', linewidth=.2)
        axR.grid(b=True, which='major', axis='both', linewidth=1)
        
        plt.tight_layout()
        
        return
        
    def plotStates(self, t=None, states=None, pulses=None, labels=None, phiOn=0, peaks=None, name=None): ### Check how to check for optional arguments
        # Consider removing arguments t,states,pulses,labels...
        
        if t is None:
            t = self.t
        
        if states is None:
            states = self.states
        
        if pulses is None:
            pulses = self.t[self.pulseInd]
        
        if labels is None:
            labels = self.stateLabels
        
        
        
        if peaks is not None and len(peaks) > 0:
            plotPieCharts = True
        else:
            plotPieCharts = False
        
        figWidth, figHeight = mpl.rcParams['figure.figsize']
        fig = plt.figure(figsize=(figWidth, 1.5*figHeight))
        gs = plt.GridSpec(3,3)
        
        begT, endT = t[0], t[-1]
        
        # Plot line graph of states
        axLine = fig.add_subplot(gs[0,:])
        plt.plot(t,states)
        plt.setp(axLine.get_xticklabels(), visible=False)
        plotSum = False
        if plotSum:
            sig, = plt.plot(t, np.sum(states,axis=1), color='k', linestyle='--')
            labelsIncSum = np.append(labels,'$\Sigma s_i$')
            plt.legend(labelsIncSum, loc=6)
        else:
            plt.legend(labels, loc=6)
        plt.ylabel('$\mathrm{State\ occupancy}$')# proportion')
        plt.xlim((begT, endT)) #plt.xlim((0,delD+(nPulses*(onD+offD)))) # t_run
        #plt.ylim((-0.1,1.1))
        plt.ylim((0,1))
        if config.addTitles:
            plt.title('$\mathrm{State\ variables\ through\ time}$') #plt.title('State variables through time: $v={} \mathrm{{mV}},\ \phi={:.3g} \mathrm{{photons}} \cdot \mathrm{{s}}^{{-1}} \cdot \mathrm{{cm}}^{{-2}}$'.format(V,phiOn))
        plotLight(pulses, axLine)
        ### New plot format (plus change in ylims)
        #axLine.spines['left'].set_position('zero') # y-axis
        #axLine.spines['right'].set_color('none')
        #axLine.spines['bottom'].set_position('zero') # x-axis
        axLine.spines['bottom'].set_color('none')
        axLine.spines['top'].set_color('none')
        axLine.spines['left'].set_smart_bounds(True)
        axLine.spines['bottom'].set_smart_bounds(True)
        #axLine.xaxis.set_ticks_position('bottom')
        #axLine.yaxis.set_ticks_position('left')
        ##########################################
        
        ### Plot stack plot of state variables
        axStack = fig.add_subplot(gs[1,:], sharex=axLine)
        plt.stackplot(t,states.T)
        plt.ylim((0,1))
        plt.xlim((begT, endT)) #plt.xlim((0,delD+(nPulses*(onD+offD))))
        plotLight(pulses, axStack, 'borders')
        if config.addTitles:
            axStack.title.set_visible(False)
        plt.xlabel('$\mathrm{Time\ [ms]}$')
        plt.ylabel('$\mathrm{State\ occupancy}$')# proportion')
        
        if plotPieCharts:
            axS0 = fig.add_subplot(gs[2,0])
            initialStates = self.s0 * 100
            if verbose > 1:
                pct = {l:s for l,s in zip(labels,sizes)}
                print('Initial state occupancies (%):',sorted(pct.items(),key=lambda x: labels.index(x[0])))
            patches, texts, autotexts = plt.pie(initialStates, labels=labels, autopct='%1.1f%%', startangle=90, shadow=False) #, explode=explode
            for lab in range(len(labels)):
                texts[lab].set_fontsize(mpl.rcParams['ytick.labelsize'])
                autotexts[lab].set_fontsize(mpl.rcParams['axes.labelsize'])
            plt.axis('equal')
            if config.addTitles:
                plt.title('$\mathrm{Initial\ state\ occupancies}$')
            #else:
            #    plt.title('$t_{0}$')
            
            if peaks is not None: ### Plot peak state proportions
                pInd = peaks[0] # Plot the first peak
                axLine.axvline(x=t[pInd],linestyle=':',color='k')
                axStack.axvline(x=t[pInd],linestyle=':',color='k')
                axPeak = fig.add_subplot(gs[2,1])
                sizes = states[pInd,:] * 100
                #sizes = [s*100 for s in sizes]
                #explode = (0,0,0.1,0.1,0,0)
                if verbose > 1:
                    pct = {l:s for l,s in zip(labels,sizes)}
                    print('Peak state occupancies (%):',sorted(pct.items(),key=lambda x: labels.index(x[0])))
                patches, texts, autotexts = plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, shadow=False)#, explode=explode)
                for lab in range(len(labels)):
                    texts[lab].set_fontsize(mpl.rcParams['ytick.labelsize'])
                    autotexts[lab].set_fontsize(mpl.rcParams['axes.labelsize'])
                plt.axis('equal')
                if config.addTitles:
                    plt.title('$\mathrm{Simulated\ peak\ state\ occupancies}$')
                #else:
                #    plt.title('$t_{peak}$')
            
            if phiOn > 0: ### Plot steady state proportions
                axSS = fig.add_subplot(gs[2,2])
                steadyStates = self.calcSteadyState(phiOn) * 100 # Convert array of proportions to %
                #steadyStates = [s*100 for s in steadyStates]
                #explode = (0,0,0.1,0.1,0,0)
                if verbose > 1:
                    pct = {l:s for l,s in zip(labels,sizes)}
                    print('Steady state occupancies (%):',sorted(pct.items(),key=lambda x: labels.index(x[0])))
                patches, texts, autotexts = plt.pie(steadyStates, labels=labels, autopct='%1.1f%%', startangle=90, shadow=False) #, explode=explode
                for lab in range(len(labels)):
                    texts[lab].set_fontsize(mpl.rcParams['ytick.labelsize'])
                    autotexts[lab].set_fontsize(mpl.rcParams['axes.labelsize'])
                plt.axis('equal')
                if config.addTitles:
                    plt.title('$\mathrm{Analytic\ steady\ state\ occupancies}$')
                #else:
                #    plt.title('$t_{\inf}$')

        plt.tight_layout()
        
        if name is not None:
            from os import path
            figName = path.join(fDir, name+'.'+config.saveFigFormat)
            plt.savefig(figName, format=config.saveFigFormat)


class RhO_3states(RhodopsinModel):
    """Class definition for the 3-state model"""
    
    # Class attributes
    nStates = 3
    useAnalyticSoln = True
    
    s_0 = np.array([1,0,0])             # Default: Initialise in dark 
    phi_0 = 0.0                         # Default flux level in dark-adapted state
    stateVars = ['C','O','D']           # stateVars[0] is the 'ground' state
    stateLabels = ['$C$','$O$','$D$']
    photoFuncs = ['_calcGa', '_calcGr'] # {'Ga':'_calcGa', 'Gr':'_calcGr'} --> photoRates['Ga'](phi)
    photoRates = ['Ga', 'Gr']
    photoLabels = ['$G_a$', '$G_r$'] # {'Ga':'$G_a$', 'Gr':'$G_r$'}
    constRates = ['Gd']
    constLabels = ['$G_d$']
    
    paramsList = ['g0', 'phi_m', 'k', 'p', 'Gd', 'Gr0', 'Gr1', 'E', 'v0', 'v1'] # List of model constants    

    connect = [[0,1,0],
               [0,0,1],
               [1,0,0]]
    
    conDir  = [[ 0,-1, 1],
               [ 1, 0,-1],
               [-1, 1, 0]]
    
    equations = """
                $$ \dot{C} = G_{r}(\phi)D - G_{a}(\phi)C $$
                $$ \dot{O} = G_{a}(\phi)C - G_{d}O $$
                $$ \dot{D} = G_{d}O - G_{r}(\phi)D $$
                $$ C + O + D = 1 $$
                $$ $$
                $$ G_a(\phi) = k\\frac{\phi^p}{\phi^p + \phi_m^p} $$
                $$ G_r(\phi) = G_{r0} + \mathcal{H}(\phi) \cdot G_{r1} $$
                $$ $$
                $$ f_{\phi}(\phi) = O \qquad \qquad $$
                $$ f_v(v) = \\frac{1-\\exp({-(v-E)/v_0})}{(v-E)/v_1} $$
                $$ I_{\phi} = g_0 \cdot f_{\phi}(\phi) \cdot f_v(v) \cdot (v-E) $$
                """
    
    _latex =   ["$\dot{C} = G_{r}(\phi)D - G_{a}(\phi)C$", 
                "$\dot{O} = G_{a}(\phi)C - G_{d}O$",
                "$\dot{D} = G_{d}O - G_{r}(\phi)D$",
                "$C + O + D = 1$",
                "$G_a(\phi) = k\\frac{\phi^p}{\phi^p + \phi_m^p}$",
                "$G_r(\phi) = G_{r0} + \mathcal{H}(\phi) \cdot G_{r1}$",
                "$f_{\phi}(\phi) = O$"
                "$f_v(v) = \\frac{1-\\exp({-(v-E)/v_0})}{(v-E)/v_1}$",
                "$I_{\phi} = g_0 \cdot f_{\phi}(\phi) \cdot f_v(v) \cdot (v-E)$"]
    # $$ G_r = G_{r0} + G_{r1}(\phi) $$
    #"""
    #\begin{align*}
    #\frac{dC}{dt} &= G_{r}D - P C \\
    #\frac{dO}{dt} &= P C -G_{d}O \\
    #\frac{dD}{dt} &= G_{d}O-G_{r}D \\
    #C+O+D &= 1 \\
    #P &= \phi\frac{\epsilon \sigma_{ret}}{w_{loss}} \\
    #G_r &= G_{r,d} + \mathcal{H}(\phi) \cdot G_{r,l} \\
    #I_{\phi} &= \bar{g} O \cdot (v-E)
    #\end{align}
    #"""                
                
    eqIss = """$I_{SS} = \bar{g_0} \cdot \frac{G_a \cdot G_r}{G_d \cdot (G_r + G_a) + G_a \cdot G_r} \cdot (v-E) 
    = \bar{g_0} \cdot \frac{\tau_d}{\tau_d + \tau_r + \tau_\phi} \cdot (v-E)$"""
    
    brianStateVars = ['C','O','D'] #['S_C','S_O','S_D']
    
    """
    brian = '''
            dS_C/dt = Gr*S_D - Ga*S_C               : 1
            dS_O/dt = Ga*S_C - Gd*S_O               : 1
            dS_D/dt = Gd*S_O - Gr*S_D               : 1
            Ga = k*((phi**p)/(phi**p + phi_m**p))   : second**-1
            Gr = Gr0 + int(stimulus)*Gr1           : second**-1
            f_phi = S_O                             : 1
            f_v = (1-exp(-(v-E)/v0))/((v-E)/v1)     : 1
            I = g0*f_phi*f_v*(v-E)                  : amp
            phi                                     : metre**-2*second**-1 (shared)
            stimulus                               : boolean (shared)
            '''
    """
    
    """
    brian = '''
            dS_C/dt = Gr*S_D - Ga*S_C               : 1
            dS_O/dt = Ga*S_C - Gd*S_O               : 1
            dS_D/dt = Gd*S_O - Gr*S_D               : 1
            Ga = k*((phi**p)/(phi**p + phi_m**p))   : second**-1
            Gr = Gr0 + Theta*Gr1                    : second**-1
            f_phi = S_O                             : 1
            f_v = (1-exp(-(v-E)/v0))/((v-E)/v1)     : 1
            I = g0*f_phi*f_v*(v-E)                  : amp
            phi                                     : metre**-2*second**-1 (shared)
            Theta = int(phi > 0*phi)                : 1 (shared)
            '''
    """
    
    brian = '''
            dC/dt = Gr*D - Ga*C                     : 1
            dO/dt = Ga*C - Gd*O                     : 1
            dD/dt = Gd*O - Gr*D                     : 1
            Ga = k*((phi**p)/(phi**p + phi_m**p))   : second**-1
            Gr = Gr0 + Theta*Gr1                    : second**-1
            f_phi = O                               : 1
            f_v = (1-exp(-(v-E)/v0))/((v-E)/v1)     : 1
            I = g0*f_phi*f_v*(v-E)                  : amp
            phi                                     : metre**-2*second**-1 (shared)
            Theta = int(phi > 0*phi)                : 1 (shared)
            '''
    #S_D = 1 - S_C - S_O : 1 #
    #int(phi>0)
    #Ga = stimulus*k*((phi**p)/(phi**p+phi_m**p)) : second**-1
    #H = stimulus*((phi**p)/(phi**p+phi_m**p)) : 1
    #Ga = k * H : second**-1
    """
    brian_phi_t = '''
            dS_C/dt = Gr*S_D - Ga*S_C                   : 1
            dS_O/dt = Ga*S_C - Gd*S_O                   : 1
            dS_D/dt = Gd*S_O - Gr*S_D                   : 1
            Ga = k*((phi(t)**p)/(phi(t)**p + phi_m**p)) : second**-1
            Gr = Gr0 + Theta*Gr1                        : second**-1
            f_phi = S_O                                 : 1
            f_v = (1-exp(-(v-E)/v0))/((v-E)/v1)         : 1
            I = g0*f_phi*f_v*(v-E)                      : amp
            Theta = int(phi(t) > 0*phi(t))              : 1 (shared)
            '''
            #stimulus = int(ceil(clip(phi(t), 0, 1))) : boolean (shared)
            # mmetre**-2*second**-1
            #S_D = 1 - S_C - S_O : 1
    """
    brian_phi_t = '''
            dC/dt = Gr*D - Ga*C                         : 1
            dO/dt = Ga*C - Gd*O                         : 1
            dD/dt = Gd*O - Gr*D                         : 1
            Ga = k*((phi(t)**p)/(phi(t)**p + phi_m**p)) : second**-1
            Gr = Gr0 + Theta*Gr1                        : second**-1
            f_phi = O                                   : 1
            f_v = (1-exp(-(v-E)/v0))/((v-E)/v1)         : 1
            I = g0*f_phi*f_v*(v-E)                      : amp
            Theta = int(phi(t) > 0*phi(t))              : 1 (shared)
            '''
            
    def reportParams(self): # Replace with local def __str__(self):
        report =  'Three-state model parameters\n'
        report += '============================\n'
        report += 'E    = {:12.3g}\n'.format(self.E)
        report += 'k    = {:12.3g}\n'.format(self.k)
        report += 'phi_m = {:12.3g}\n'.format(self.phi_m)
        report += 'p    = {:12.3g}\n'.format(self.p)
        report += 'Gd   = {:12.3g}\n'.format(self.Gd)
        report += 'Gr0  = {:12.3g}\n'.format(self.Gr0)
        report += 'Gr1  = {:12.3g}\n'.format(self.Gr1)
        report += 'g0   = {:12.3g}\n'.format(self.g0)
        report += '----------------------------'
        return report
        

    
    def _calcGa(self, phi):
        #return self.k * phi
        #return 0.5 * phi * (1.2e-8 * 1e-6) / 1.1  # eps * phi * sigma_ret (mm^-2) / wloss
        #return self.k * phi #(1 - np.exp(-phi/self.phiSat))
        return self.k * phi**self.p/(phi**self.p + self.phi_m**self.p)
    
    def _calcGr(self, phi):
        return self.Gr0 + (phi>0)*self.Gr1
        #return self.Gr0 + self.Gr1 * np.log(1 + phi/self.phi0) # self.Gr0 + self.Gr1
        #return self.Gr_dark + self.Gr_light * np.log(1 + phi/self.phi0) # self.Gr0 + self.Gr1
        # return 1/(taur_dark*exp(-log(1+phi/phi0))+taur_min) # Fig 6 Nikolic et al. 2009
        ### return Gr_dark + kr*(1-exp(-phi/phi0)) # a = Gr_max - Gr_dark
        
    #def set_Gd(self, phi):
    #    return 1/(taud_dark - a*log(1+phi/phi0)) # Fig 6 Nikolic et al. 2009
    
    def setLight(self, phi):
        """Set transition rates according to the instantaneous photon flux density"""
        #assert(phi >= 0)
        if phi < 0:
            phi = 0
        self.phi = phi
        self.Ga = self._calcGa(phi)
        self.Gr = self._calcGr(phi)
        if verbose > 1:
            self.dispRates()
    
    def dispRates(self):
        print("Transition rates (phi={:.3g}): C --[Ga={:.3g}]--> O --[Gd={:.3g}]--> D --[Gr={:.3g}]--> C".format(self.phi,self.Ga,self.Gd,self.Gr))
    
    def solveStates(self, s_0, t, phi_t=None): # solveStatesPhi_t http://stackoverflow.com/questions/5649313/a-possible-bug-in-odeint-interp1d-interplay
        """Function describing the differential equations of the 3-state model to be solved by odeint"""
        # Add interpolation of values for phi(t) to initialisation f_phi = interp1d(t,sin(w*t),kind='cubic')
        # Then pass as an argument to integrator: odeint(func, y0, t, args=())
        
        if phi_t is not None:
            self.setLight(float(phi_t(t)))
            #print("dydt: phi_t({})={}".format(t,phi_t(t)))
        C,O,D = s_0 # Split state vector into individual variables s1=s[0], s2=s[1], etc
        dCdt = -self.Ga*C +             self.Gr*D   # C'
        dOdt =  self.Ga*C - self.Gd*O               # O'
        dDdt =              self.Gd*O - self.Gr*D   # D'
        #f2 = -(f0+f1)
        return np.array([ dCdt, dOdt, dDdt ])
    
    def jacobian(self, s_0, t, phi_t=None): # jacobianPhi_t
        #print("Jac: phi_t({})={}".format(t,phi_t(t)))
        #self.setLight(phi_t(t))
        # Jacobian matrix used to improve precision / speed up ODE solver
        # jac[i,j] = df[i]/dy[j]; where y'(t) = f(t,y)
        return np.array([[-self.Ga, 0, self.Gr],    # [dCdt/dC, dCdt/dO, dCdt/dD]
                         [self.Ga, -self.Gd, 0],    # [dOdt/dC, dOdt/dO, dOdt/dD]
                         [0, self.Gd, -self.Gr]])   # [dDdt/dC, dDdt/dO, dDdt/dD]
    
    # def hessian(self, s_0, t):
        # Hessian matrix for scipy.optimize.minimize (Only for Newton-CG, dogleg, trust-ncg.)
        # H(f)_ij(X) = D_iD_jf(X)
        # return np.array([[0, 0, 0],
        #                 [0, 0, 0],
        #                 [0, 0, 0]])
    
    '''
    def calcI(self, V, states=None):
        """Calculate the photocurrent from the cell membrane voltage and state matrix"""
        if states is None:
            states = self.states
        O = states[:,1] # time x C,O,D
        I_RhO = self.g0*O*self.calcfV(V)*(V-self.E)
        return I_RhO * 1e-6 # pS * mV * 1e-6 = nA
    '''
    
    def calcfphi(self, states=None):#, gam=None):
        if states is None:
            states = self.states
        C, O, D = states.T
        #if gam is None:
        #    gam = self.gam
        return O
    
    # def calcOn(self,t):
        # """Calculate the on phase current for square light pulses from the analytic solution"""
        # r = np.array([lam1, lam2])
        # k = np.array([a1, a2])
        # I = k * np.exp(-r*t)
        # -(a0 + a1*(1-np.exp(-t/tau_act)) + a2*np.exp(-t/tau_deact))
        # pass
    
    # def calcOff():
        # """Calculate the off phase current for square light pulses from the analytic solution"""
        # -(A*np.exp(-Gd*t))
        # pass
    
    def calcSteadyState(self, phi):
        self.setLight(phi)
        denom3 = self.Gd * (self.Gr + self.Ga) + self.Ga * self.Gr
        Cs = self.Gd*self.Gr/denom3
        Os = self.Ga*self.Gr/denom3
        Ds = self.Ga*self.Gd/denom3
        self.steadyStates = np.array([Cs, Os, Ds])
        return np.array([Cs, Os, Ds])
    
    def calcSoln(self, t, s0=[1,0,0]): #RhO_3states.s_0
        [C_0, O_0, D_0] = s0
        Ga = self.Ga
        Gd = self.Gd
        Gr = self.Gr
        #if t[0] > 0: # Shift time array to start at 0
        t = t - t[0] # Shift time array forwards or backwards to start at 0
        
        SP = Ga*Gd + Ga*Gr + Gd*Gr
        SQ = Ga**2 + Gd**2 + Gr**2
        if 2*SP > SQ:
            if verbose > 1:
                print('Imaginary solution! SP = {}; SQ = {} --> (SQ-2*SP)**(1/2) = NaN'.format(SP, SQ))
            return odeint(self.solveStates, s0, t, Dfun=self.jacobian)
            #raise ValueError() # Uncomment this when error catching is implemented
        #else:
        RSD = (SQ-2*SP)**(1/2) # xi
        lambda_1 = (Ga + Gd + Gr + RSD)/2
        lambda_2 = (Ga + Gd + Gr - RSD)/2
        Z_1 = C_0*Gd*Ga + O_0*(Gd*(Ga - lambda_1)) + D_0*Gr*(Gr-lambda_2)
        Z_2 = C_0*Gd*Ga + O_0*(Gd*(Ga - lambda_2)) + D_0*Gr*(Gr-lambda_1)
        Exp_1 = np.exp(-t*lambda_1)
        Exp_2 = np.exp(-t*lambda_2)
        
        C = (Z_1*lambda_2*(lambda_1-Gd-Gr)*Exp_1 - Z_2*lambda_1*(lambda_2-Gd-Gr)*Exp_2 + (RSD*Gd**2*Gr*(C_0+D_0+O_0)))/(Gd*SP*RSD)
        O = (-Z_1*lambda_2*(lambda_1-Gr)*Exp_1 + Z_2*lambda_1*(lambda_2-Gr)*Exp_2 + (RSD*Ga*Gd*Gr*(C_0+D_0+O_0)))/(Gd*SP*RSD)
        D = (Z_1*lambda_2*Exp_1 - Z_2*lambda_1*Exp_2 + (RSD*Gd*Ga*(C_0+D_0+O_0)))/(SP*RSD)
        
        return np.column_stack((C,O,D)) #np.row_stack((C,O,D)).T #np.column_stack((C.T,O.T,D.T))
        
    # def calcSoln(self, t, s0=[1,0,0]):
        # [C_0,O_0,D_0] = s0
        # P = self.P
        # Gd = self.Gd
        # Gr = self.Gr
        # #if t[0] > 0: # Shift time array to start at 0
        # t = t - t[0] # Shift time array forwards or backwards to start at 0
        
        
        # SP = P*Gd + P*Gr + Gd*Gr
        # SQ = P**2 + Gd**2 + Gr**2
        # lambda_1 = (Gd + Gr + P + (SQ-2*SP)**(1/2))/2
        # lambda_2 = (Gd + Gr + P - (SQ-2*SP)**(1/2))/2
        # Den_1 = (2*SP*(SQ-2*SP)**(1/2))
        # Fac_1 = (C_0*Gd*P**2 + C_0*Gd**2*P + Gd*Gr**2*D_0 - Gd**2*Gr*D_0 - 2*Gd**2*Gr*O_0 - Gr*D_0*P**2 + Gr**2*D_0*P + Gd*O_0*P**2 - Gd**2*O_0*P + C_0*Gd*Gr*P - Gd*Gr*O_0*P - C_0*Gd*P*(SQ-2*SP)**(1/2) + Gd*Gr*D_0*(SQ-2*SP)**(1/2) + Gr*D_0*P*(SQ-2*SP)**(1/2) - Gd*O_0*P*(SQ-2*SP)**(1/2))
        # Fac_2 = (C_0*Gd*P**2 + C_0*Gd**2*P + Gd*Gr**2*D_0 - Gd**2*Gr*D_0 - 2*Gd**2*Gr*O_0 - Gr*D_0*P**2 + Gr**2*D_0*P + Gd*O_0*P**2 - Gd**2*O_0*P + C_0*Gd*Gr*P - Gd*Gr*O_0*P + C_0*Gd*P*(SQ-2*SP)**(1/2) - Gd*Gr*D_0*(SQ-2*SP)**(1/2) - Gr*D_0*P*(SQ-2*SP)**(1/2) + Gd*O_0*P*(SQ-2*SP)**(1/2))
    
        # C = (np.exp(-t*lambda_1)*np.exp(-t*lambda_2)*((P*np.exp(t*lambda_2)*Fac_1)/(2*(SP)) + (P*np.exp(t*lambda_1)*Fac_2)/(2*(SP)) + (P**2*np.exp(t*lambda_2)*Fac_1)/(2*(SP)*(SQ-2*SP)**(1/2)) - (P**2*np.exp(t*lambda_1)*Fac_2)/(2*(SP)*(SQ-2*SP)**(1/2)) - (Gd*P*np.exp(t*lambda_2)*Fac_1)/(2*(SP)*(SQ-2*SP)**(1/2)) - (Gr*P*np.exp(t*lambda_2)*Fac_1)/(2*(SP)*(SQ-2*SP)**(1/2)) + (Gd*P*np.exp(t*lambda_1)*Fac_2)/(2*(SP)*(SQ-2*SP)**(1/2)) + (Gr*P*np.exp(t*lambda_1)*Fac_2)/(2*(SP)*(SQ-2*SP)**(1/2)) + (2*Gd**2*Gr*P*np.exp(t*lambda_1)*np.exp(t*lambda_2)*(C_0 + D_0 + O_0))/(SP)))/(2*Gd*P)
        
        # O = -(np.exp(-t*lambda_1)*np.exp(-t*lambda_2)*((np.exp(t*lambda_1)*Fac_2)/(2*(SP)) + (np.exp(t*lambda_2)*Fac_1)/(2*(SP)) - (Gd*np.exp(t*lambda_1)*Fac_2)/(2*(SP)*(SQ-2*SP)**(1/2)) + (Gr*np.exp(t*lambda_1)*Fac_2)/(2*(SP)*(SQ-2*SP)**(1/2)) - (P*np.exp(t*lambda_1)*Fac_2)/(2*(SP)*(SQ-2*SP)**(1/2)) + (Gd*np.exp(t*lambda_2)*Fac_1)/(2*(SP)*(SQ-2*SP)**(1/2)) - (Gr*np.exp(t*lambda_2)*Fac_1)/(2*(SP)*(SQ-2*SP)**(1/2)) + (P*np.exp(t*lambda_2)*Fac_1)/(2*(SP)*(SQ-2*SP)**(1/2)) - (2*Gd*Gr*P*np.exp(t*lambda_1)*np.exp(t*lambda_2)*(C_0 + D_0 + O_0))/(SP)))/(2*Gd)
        
        # D = np.exp(-t*lambda_1)*np.exp(-t*lambda_2)*((np.exp(t*lambda_2)*Fac_1)/(2*(SP)*(SQ-2*SP)**(1/2)) - (np.exp(t*lambda_1)*Fac_2)/(2*(SP)*(SQ-2*SP)**(1/2)) + (Gd*P*np.exp(t*lambda_1)*np.exp(t*lambda_2)*(C_0 + D_0 + O_0))/(SP))
        
        # return np.row_stack((C,O,D)).T #np.column_stack((C.T,O.T,D.T))
    
    

class RhO_4states(RhodopsinModel):
    """Class definition for the 4-state model"""
    
    # Class attributes
    nStates = 4
    useAnalyticSoln = False
    
    phi_0 = 0.0                         # Instantaneous Light flux
    s_0 = np.array([1,0,0,0])           # Default: Initialise in the dark    
    stateVars = ['C1','O1','O2','C2']   # stateVars[0] is the 'ground' state
    stateLabels = ['$C_1$','$O_1$','$O_2$','$C_2$'] # [texIt(s) for s in stateVars]
    
    photoFuncs = ['_calcGa1', '_calcGa2', '_calcGf', '_calcGb']
    photoRates = ['Ga1', 'Ga2', 'Gf', 'Gb']
    photoLabels = ['$G_{a1}$', '$G_{a2}$', '$G_{f}$', '$G_{b}$', '$G_{d1}$', '$G_{d2}$']
    constRates = ['Gd1', 'Gd2', 'Gr0']
    constLabels = ['$G_{d1}$', '$G_{d2}$', '$G_{r0}$']
    
    paramsList = ['g0', 'gam', 'phi_m', 'k1', 'k2', 'p', 'Gf0', 'k_f', 'Gb0', 'k_b', 'q', 'Gd1', 'Gd2', 'Gr0', 'E', 'v0', 'v1'] # List of model constants
    
    connect = [[0,1,0,0],
               [1,0,1,0],
               [0,1,0,1],
               [1,0,1,0]]
    
    equations = """
                $$ \dot{C_1} = G_{r}C_2 + G_{d1}O_1 - G_{a1}(\phi)C_1 $$
                $$ \dot{O_1} = G_{a1}(\phi)C_1 - (G_{d1}+G_{f}(\phi))O_1 + G_{b}(\phi)O_2 $$
                $$ \dot{O_2} = G_{a2}(\phi)C_2 + G_{f}(\phi)O_1 - (G_{d2}+G_{b}(\phi))O_2 $$
                $$ \dot{C_2} = G_{d2}O_2 - (G_{a2}(\phi)+G_{r0})C_2 $$
                $$ C_1 + O_1 + O_2 + C_2 = 1 $$
                $$$$
                $$ G_{a1}(\phi) = k_1\\frac{\phi^p}{\phi^p + \phi_m^p} $$
                $$ G_{f}(\phi) = G_{f0} + k_{f} \\frac{\phi^q}{\phi^q + \phi_m^q} $$
                $$ G_{b}(\phi) = G_{b0} + k_{b} \\frac{\phi^q}{\phi^q + \phi_m^q} $$
                $$ G_{a2}(\phi) = k_2\\frac{\phi^p}{\phi^p + \phi_m^p} $$
                $$$$
                $$ f_{\phi}(\phi) = O_1+\gamma O_2 $$
                $$ f_v(v) = \\frac{1-\\exp({-(v-E)/v_0})}{(v-E)/v_1} $$
                $$ I_{\phi} = g_0 \cdot f_{\phi}(\phi) \cdot f_v(v) \cdot (v-E) $$
                """     
    
                # """
                # $$ \dot{C_{\\alpha}} = G_{r}C_{\\beta} + G_{d{\\alpha}}O_{\\alpha} - G_{a{\\alpha}}(\phi)C_{\\alpha} $$
                # $$ \dot{O_{\\alpha}} = G_{a{\\alpha}}(\phi)C_{\\alpha} - (G_{d{\\alpha}}+G_{f}(\phi))O_{\\alpha} + G_{b}(\phi)O_{\\beta} $$
                # $$ \dot{O_{\\beta}} = G_{a{\\beta}}(\phi)C_{\\beta} + G_{f}(\phi)O_{\\alpha} - (G_{d{\\beta}}+G_{b}(\phi))O_{\\beta} $$
                # $$ \dot{C_{\\beta}} = G_{d{\\beta}}O_{\\beta} - (G_{a{\\beta}}(\phi)+G_{r0})C_{\\beta} $$
                # $$ C_{\\alpha} + O_{\\alpha} + O_{\\beta} + C_{\\beta} = 1 $$
                # $$$$
                # $$ G_{a{\\alpha}}(\phi) = k_{\\alpha}\\frac{\phi^p}{\phi^p + \phi_m^p} $$
                # $$ G_{a{\\beta}}(\phi) = k_{\\beta}\\frac{\phi^p}{\phi^p + \phi_m^p} $$
                # $$ G_{f}(\phi) = G_{f0} + k_{f} \\frac{\phi^q}{\phi^q + \phi_m^q} $$
                # $$ G_{b}(\phi) = G_{b0} + k_{b} \\frac{\phi^q}{\phi^q + \phi_m^q} $$
                # $$$$
                # $$ f(v) = \\frac{1-\\exp({-(v-E)/v_0})}{(v-E)/v_1} $$
                # $$ I_{\phi} = g (O_{\\alpha}+\gamma O_{\\beta}) f(v) (v-E) $$
                # """     

    brianStateVars = ['C_1','O_1','O_2','C_2'] #['S_C1','S_O1','S_O2','S_C2']
    """
    brian = '''
            dS_C1/dt = Gr0*S_C2 + Gd1*S_O1 - Ga1*S_C1 : 1
            dS_O1/dt = Ga1*S_C1 - (Gd1+Gf)*S_O1 + Gb*S_O2 : 1
            dS_O2/dt = Ga2*S_C2 + Gf*S_O1 - (Gd2+Gb)*S_O2 : 1
            S_C2 = 1 - S_C1 - S_O1 - S_O2 : 1
            H_p = int(stimulus)*((phi**p)/(phi**p+phi_m**p)) : 1
            H_q = int(stimulus)*((phi**q)/(phi**q+phi_m**q)) : 1
            Ga1 = k1*H_p : second**-1
            Ga2 = k2*H_p : second**-1
            Gf = Gf0 + kf*H_q : second**-1
            Gb = Gb0 + kb*H_q : second**-1
            f_v = (1-exp(-(v-E)/v0))/((v-E)/v1) : 1
            f_phi = S_O1+gam*S_O2 : 1
            I = g0*f_phi*f_v*(v-E) : amp
            phi : metre**-2*second**-1 (shared)
            stimulus : boolean (shared)
            '''
    """
    
    brian = '''
            dC_1/dt = Gr0*C_2 + Gd1*O_1 - Ga1*C_1 : 1
            dO_1/dt = Ga1*C_1 - (Gd1+Gf)*O_1 + Gb*O_2 : 1
            dO_2/dt = Ga2*C_2 + Gf*O_1 - (Gd2+Gb)*O_2 : 1
            C_2 = 1 - C_1 - O_1 - O_2 : 1
            H_p = Theta*((phi**p)/(phi**p+phi_m**p)) : 1
            H_q = Theta*((phi**q)/(phi**q+phi_m**q)) : 1
            Ga1 = k1*H_p : second**-1
            Ga2 = k2*H_p : second**-1
            Gf = Gf0 + k_f*H_q : second**-1
            Gb = Gb0 + k_b*H_q : second**-1
            f_v = (1-exp(-(v-E)/v0))/((v-E)/v1) : 1
            f_phi = O_1+gam*O_2 : 1
            I = g0*f_phi*f_v*(v-E) : amp
            phi : metre**-2*second**-1 (shared)
            Theta = int(phi > 0*phi)                : 1 (shared)
            '''
            
    #phi : meter**-2*second**-1
    """
    brian_phi_t = '''
            dS_C1/dt = Gr0*S_C2 + Gd1*S_O1 - Ga1*S_C1 : 1
            dS_O1/dt = Ga1*S_C1 - (Gd1+Gf)*S_O1 + Gb*S_O2 : 1
            dS_O2/dt = Ga2*S_C2 + Gf*S_O1 - (Gd2+Gb)*S_O2 : 1
            S_C2 = 1 - S_C1 - S_O1 - S_O2 : 1
            H_p = Theta*((phi(t)**p)/(phi(t)**p+phi_m**p)) : 1
            H_q = Theta*((phi(t)**q)/(phi(t)**q+phi_m**q)) : 1
            Ga1 = k1*H_p : second**-1
            Ga2 = k2*H_p : second**-1
            Gf = Gf0 + kf*H_q : second**-1
            Gb = Gb0 + kb*H_q : second**-1
            f_v = (1-exp(-(v-E)/v0))/((v-E)/v1) : 1
            f_phi = S_O1+gam*S_O2 : 1
            I = g0*f_phi*f_v*(v-E) : amp
            Theta = int(phi(t) > 0*phi(t)) : boolean (shared)
            '''
    """
    """
    brian_phi_t = '''
            dS_C1/dt = Gr0*S_C2 + Gd1*S_O1 - Ga1*S_C1 : 1
            dS_O1/dt = Ga1*S_C1 - (Gd1+Gf)*S_O1 + Gb*S_O2 : 1
            dS_O2/dt = Ga2*S_C2 + Gf*S_O1 - (Gd2+Gb)*S_O2 : 1
            S_C2 = 1 - S_C1 - S_O1 - S_O2 : 1
            Ga1 = Theta*k1*phi(t)**p/(phi(t)**p+phi_m**p) : second**-1
            Ga2 = Theta*k2*phi(t)**p/(phi(t)**p+phi_m**p) : second**-1
            Gf = Gf0 + Theta*kf*phi(t)**q/(phi(t)**q+phi_m**q) : second**-1
            Gb = Gb0 + Theta*kb*phi(t)**q/(phi(t)**q+phi_m**q) : second**-1
            f_v = (1-exp(-(v-E)/v0))/((v-E)/v1) : 1
            f_phi = S_O1+gam*S_O2 : 1
            I = g0*f_phi*f_v*(v-E) : amp
            Theta = int(phi(t) > 0*phi(t)) : boolean (shared)
            '''
    """
    
    brian_phi_t = '''
            dC_1/dt = Gr0*C_2 + Gd1*O_1 - Ga1*C_1 : 1
            dO_1/dt = Ga1*C_1 - (Gd1+Gf)*O_1 + Gb*O_2 : 1
            dO_2/dt = Ga2*C_2 + Gf*O_1 - (Gd2+Gb)*O_2 : 1
            C_2 = 1 - C_1 - O_1 - O_2 : 1
            Ga1 = Theta*k1*phi(t)**p/(phi(t)**p+phi_m**p) : second**-1
            Ga2 = Theta*k2*phi(t)**p/(phi(t)**p+phi_m**p) : second**-1
            Gf = Gf0 + Theta*k_f*phi(t)**q/(phi(t)**q+phi_m**q) : second**-1
            Gb = Gb0 + Theta*k_b*phi(t)**q/(phi(t)**q+phi_m**q) : second**-1
            f_v = (1-exp(-(v-E)/v0))/((v-E)/v1) : 1
            f_phi = O_1+gam*O_2 : 1
            I = g0*f_phi*f_v*(v-E) : amp
            Theta = int(phi(t) > 0*phi(t)) : 1 (shared)
            '''
    
    """
    def reportParams(self): # Replace with local def __str__(self):
        report =  'Four-state model parameters\n'
        report += '===========================\n'
        report += 'E    = {:12.3g}\n'.format(self.E)
        report += 'gam  = {:12.3g}\n'.format(self.gam)
        report += 'phi0 = {:12.3g}\n'.format(self.phi0)
        report += 'k1   = {:12.3g}\n'.format(self.k1)
        report += 'k2   = {:12.3g}\n'.format(self.k2)
        report += 'phi_m = {:12.3g}\n'.format(self.phi_m)
        report += 'p    = {:12.3g}\n'.format(self.p)
        report += 'Gr0  = {:12.3g}\n'.format(self.Gr0)
        report += 'Gd1  = {:12.3g}\n'.format(self.Gd1)
        report += 'Gd2  = {:12.3g}\n'.format(self.Gd2)
        report += 'kf   = {:12.3g}\n'.format(self.kf)
        report += 'kb   = {:12.3g}\n'.format(self.kb)
        report += 'Gf0  = {:12.3g}\n'.format(self.Gf0)
        report += 'Gb0  = {:12.3g}\n'.format(self.Gb0)
        report += 'g0   = {:12.3g}\n'.format(self.g0)
        report += '---------------------------'
        return report
    """
    
    def _calcGa1(self, phi):
        # N.B. making Ga a function of time (as in Appendix 1) results in the Six-state model
        # Gai = ei * F * f(t,tChR) See App 1
        # Ga = 1/tauChR
        #e = 0.5
        #sigma_ret = 1.2e-8 * 1e-6 # Convert from m^2 to mm^2
        #w_loss = 1.1
        #return self.k1 * phi/self.phi0 #e*phi*sigma_ret / w_loss
        #return self.k1 * (1-np.exp(-phi/self.phi0)) #e*phi*sigma_ret / w_loss
        return self.k1 * phi**self.p/(phi**self.p + self.phi_m**self.p)
    
    def _calcGa2(self, phi):
        #e = 0.15
        #sigma_ret = 1.2e-8  * 1e-6 # Convert from m^2 to mm^2
        #w_loss = 1.1
        #return self.k2 * phi/self.phi0 #e*phi*sigma_ret / w_loss
        #return self.k2 * (1-np.exp(-phi/self.phi0))
        return self.k2 * phi**self.p/(phi**self.p + self.phi_m**self.p)
    
    def _calcGf(self, phi):
        #return self.e12d + self.c1*np.log(1+(phi/self.phi0)) # e12(phi=0) = e12d
        return self.Gf0 + self.k_f * phi**self.q/(phi**self.q + self.phi_m**self.q)

    def _calcGb(self, phi):
        #return self.e21d + self.c2*np.log(1+(phi/self.phi0)) # e21(phi=0) = e21d
        return self.Gb0 + self.k_b * phi**self.q/(phi**self.q + self.phi_m**self.q)

    def setLight(self, phi):
        """Set transition rates according to the instantaneous photon flux density"""
        #assert(phi >= 0)
        if phi < 0:
            phi = 0
        self.phi = phi
        self.Ga1 = self._calcGa1(phi)
        self.Ga2 = self._calcGa2(phi)
        self.Gf = self._calcGf(phi)
        self.Gb = self._calcGb(phi)
        if verbose > 1:
            self.dispRates()
            
    def dispRates(self):
        print("Transition rates (phi={:.3g}): C1 --[Ga1={:.3g}]--> O1 --[Gf={:.3g}]--> O2".format(self.phi,self.Ga1,self.Gf))
        print("Transition rates (phi={:.3g}): O1 <--[Gb={:.3g}]-- O2 <--[Ga2={:.3g}]-- C2".format(self.phi,self.Gb,self.Ga2))
    
    def solveStates(self, s_0, t, phi_t=None):
        """Function describing the differential equations of the 4-state model to be solved by odeint"""
        if phi_t is not None:
            self.setLight(float(phi_t(t)))
        C1,O1,O2,C2 = s_0 # Split state vector into individual variables s1=s[0], s2=s[1], etc
        dC1dt = -self.Ga1*C1 +           self.Gd1*O1       +                  self.Gr0 *C2 # C1'
        dO1dt =  self.Ga1*C1 - (self.Gd1+self.Gf)*O1       +   self.Gb*O2                  # O1'
        dO2dt =                           self.Gf*O1 - (self.Gd2+self.Gb)*O2 + self.Ga2*C2 # O2'
        dC2dt =                                       self.Gd2*O2 - (self.Ga2+self.Gr0)*C2 # C2'
        #f3 = -(f0+f1+f2)
        return np.array([ dC1dt, dO1dt, dO2dt, dC2dt ])
    
    def jacobian(self, s_0, t, phi_t=None):
        # Jacobian matrix used to improve precision / speed up ODE solver
        # jac[i,j] = df[i]/dy[j]; where y'(t) = f(t,y)
        return np.array([[-self.Ga1, self.Gd1, 0, self.Gr0],
                         [self.Ga1, -(self.Gd1+self.Gf), self.Gb, 0],
                         [0, self.Gf, -(self.Gd2+self.Gb), self.Ga2],
                         [0, 0, self.Gd2, -(self.Ga2+self.Gr0)]])
    
    '''
    def calcI(self, V, states=None):
        if states is None:
            states = self.states
        O1 = states[:,1]
        O2 = states[:,2]
        I_RhO = self.g0*(O1 + self.gam*O2)*self.calcfV(V)*(V-self.E)
        return I_RhO * 1e-6 # pS * mV * 1e-6 = nA
    '''
    
    def calcfphi(self, states=None):#, gam=None):
        if states is None:
            states = self.states
        C1, O1, O2, C2 = states.T
        #if gam is None:
        gam = self.gam
        return O1 + gam * O2
    
    # def calcfV(self, V):
        # return 1
    
    def calcSteadyState(self, phi):
        self.setLight(phi)
        Ga1 = self.Ga1
        Ga2 = self.Ga2
        Gr0 = self.Gr0
        Gd1 = self.Gd1
        Gd2 = self.Gd2
        Gf = self.Gf
        Gb = self.Gb
        denom4 = Ga1 * (Gf * (Gr0 + Gd2 + Ga2) + Gb * (Gr0 + Ga2) + Gd2 * Gr0) + Gd1 * (Gb * (Gr0 + Ga2) + Gd2 * Gr0) + Gf * Gd2 * Gr0
        C1s = (Gd1 * (Gb * (Gr0 + Ga2) + Gd2 * Gr0) + Gf * Gd2 * Gr0) / denom4
        O1s = (Ga1 * (Gb * (Gr0 + Ga2) + Gd2 * Gr0)) / denom4
        O2s = (Gf * Ga1 * (Gr0 + Ga2)) / denom4
        C2s = (Gf * Ga1 * Gd2) / denom4
        self.steadyStates = np.array([C1s, O1s, O2s, C2s])
        return np.array([C1s, O1s, O2s, C2s])

    def calcSoln(self, t, s0=[1,0,0,0]):
        raise NotImplementedError(self.nStates)

    
class RhO_6states(RhodopsinModel):
    """Class definition for the 6-state model"""
    
    # Class attributes
    nStates = 6
    useAnalyticSoln = False
    s_0 = np.array([1,0,0,0,0,0])   # [s1_0=1, s2_0=0, s3_0=0, s4_0=0, s5_0=0, s6_0=0] # array not necessary
    phi_0 = 0.0                     # Default initial flux
    stateVars = ['C1','I1','O1','O2','I2','C2'] # stateVars[0] is the 'ground' state
    stateLabels = ['$C_1$','$I_1$','$O_1$','$O_2$','$I_2$','$C_2$']
    photoFuncs = ['_calcGa1', '_calcGa2', '_calcGf', '_calcGb']
    photoRates = ['Ga1', 'Ga2', 'Gf', 'Gb']
    photoLabels = ['$G_{a1}$', '$G_{a2}$', '$G_{f}$', '$G_{b}$', '$G_{d1}$', '$G_{d2}$']
    constRates = ['Go1', 'Go2', 'Gd1', 'Gd2', 'Gr0']
    constLabels = ['$G_{o1}$', '$G_{o2}$', '$G_{d1}$', '$G_{d2}$', '$G_{r0}$']
    
    paramsList = ['g0', 'gam', 'phi_m', 'k1', 'k2', 'p', 'Gf0', 'k_f', 'Gb0', 'k_b', 'q', 'Go1', 'Go2', 'Gd1', 'Gd2', 'Gr0', 'E', 'v0', 'v1'] # List of model constants    
    
    connect = [[0,1,0,0,0,0], # s_1 --> s_i=1...6
               [0,0,1,0,0,0], # s_2 -->
               [1,0,0,1,0,0],
               [0,0,1,0,0,1],
               [0,0,0,1,0,0],
               [1,0,0,0,1,0]]
    
    equations = """
                $$ \dot{C_1} = -G_{a1}(\phi)C_1 + G_{d1}O_1 + G_{r0}C_2 $$
                $$ \dot{I_1} = G_{a1}(\phi)C_1 - G_{o1}I_1 $$
                $$ \dot{O_1} = G_{o1}I_1 - (G_{d1} + G_{f}(\phi))O_1 + G_{b}(\phi)O_2 $$
                $$ \dot{O_2} = G_{f}(\phi)O_1 - (G_{b}(\phi) + G_{d2})O_2 + G_{o2}I_2 $$
                $$ \dot{I_2} = -G_{o2}I_2 + G_{a2}(\phi)C_2 $$
                $$ \dot{C_2} = G_{d2}O_2 - (G_{a2}(\phi)+G_{r0})C_2 $$
                $$ C_1 + I_1 + O_1 + O_2 + I_2 + C_2 = 1 $$
                $$$$
                $$ G_{a1}(\phi) = k_{1} \\frac{\phi^p}{\phi^p + \phi_m^p} $$
                $$ G_{f}(\phi) = G_{f0} + k_{f} \\frac{\phi^q}{\phi^q + \phi_m^q} $$
                $$ G_{b}(\phi) = G_{b0} + k_{b} \\frac{\phi^q}{\phi^q + \phi_m^q} $$
                $$ G_{a2}(\phi) = k_{2} \\frac{\phi^p}{\phi^p + \phi_m^p} $$
                $$$$
                $$ f_{\phi}(\phi) = O_1+\gamma O_2 $$
                $$ f_v(v) = \\frac{1-\\exp({-(v-E)/v_0})}{(v-E)/v_1} $$
                $$ I_{\phi} = g_0 \cdot f_{\phi}(\phi) \cdot f_v(v) \cdot (v-E) $$
                """    
    
    brianStateVars = ['C_1','I_1','O_1','O_2','I_2','C_2'] #['S_C1','S_I1','S_O1','S_O2','S_I2','S_C2']
    """
    brian = '''
            dS_C1/dt = Gr0*S_C2 + Gd1*S_O1 - Ga1*S_C1 : 1
            dS_I1/dt = Ga1*S_C1 - Go1*S_I1 : 1
            dS_O1/dt = Go1*S_I1 - (Gd1+Gf)*S_O1 + Gb*S_O2 : 1
            dS_O2/dt = Go2*S_I2 + Gf*S_O1 - (Gd2+Gb)*S_O2 : 1
            dS_I2/dt = Ga2*S_C2 - Go2*S_I2 : 1
            S_C2 = 1 - S_C1 - S_I1 - S_O1 - S_O2 - S_I2 : 1
            H_p = int(stimulus)*((phi**p)/(phi**p+phi_m**p)) : 1
            H_q = int(stimulus)*((phi**q)/(phi**q+phi_m**q)) : 1
            Ga1 = k1*H_p : second**-1
            Ga2 = k2*H_p : second**-1
            Gf = Gf0 + kf*H_q : second**-1
            Gb = Gb0 + kb*H_q : second**-1
            f_v = (1-exp(-(v-E)/v0))/((v-E)/v1) : 1
            f_phi = S_O1+gam*S_O2 : 1
            I = g0*f_phi*f_v*(v-E) : amp
            phi : metre**-2*second**-1 (shared)
            stimulus : boolean (shared) #1
            '''
    """
    
    brian = '''
            dC_1/dt = Gr0*C_2 + Gd1*O_1 - Ga1*C_1 : 1
            dI_1/dt = Ga1*C_1 - Go1*I_1 : 1
            dO_1/dt = Go1*I_1 - (Gd1+Gf)*O_1 + Gb*O_2 : 1
            dO_2/dt = Go2*I_2 + Gf*O_1 - (Gd2+Gb)*O_2 : 1
            dI_2/dt = Ga2*C_2 - Go2*I_2 : 1
            C_2 = 1 - C_1 - I_1 - O_1 - O_2 - I_2 : 1
            H_p = Theta*((phi**p)/(phi**p+phi_m**p)) : 1
            H_q = Theta*((phi**q)/(phi**q+phi_m**q)) : 1
            Ga1 = k1*H_p : second**-1
            Ga2 = k2*H_p : second**-1
            Gf = Gf0 + k_f*H_q : second**-1
            Gb = Gb0 + k_b*H_q : second**-1
            f_v = (1-exp(-(v-E)/v0))/((v-E)/v1) : 1
            f_phi = O_1+gam*O_2 : 1
            I = g0*f_phi*f_v*(v-E) : amp
            phi : metre**-2*second**-1 (shared)
            Theta = int(phi > 0*phi)                : 1 (shared)
            '''

            #'''
            #dS_C1/dt = Gr0*S_C2 + Gd1*S_O1 - Ga1*S_C1 : 1
            #dS_I1/dt = Ga1*S_C1 - Go1*S_I1 : 1
            #dS_O1/dt = Go1*S_I1 - (Gd1+Gf)*S_O1 + Gb*S_O2 : 1
            #dS_O2/dt = Go2*S_I2 + Gf*S_O1 - (Gd2+Gb)*S_O2 : 1
            #dS_I2/dt = Ga2*S_C2 - Go2*S_I2 : 1
            #S_C2 = 1 - S_C1 - S_I1 - S_O1 - S_O2 - S_I2 : 1
            #H_p = int(stimulus)*((phi**p)/(phi**p+phi_m**p)) : 1
            #H_q = int(stimulus)*((phi**q)/(phi**q+phi_m**q)) : 1
            #Ga1 = k1*H_p : second**-1
            #Ga2 = k2*H_p : second**-1
            #Gf = Gf0 + kf*H_q : second**-1
            #Gb = Gb0 + kb*H_q : second**-1
            #fv = (1-exp(-(v-E)/v0))/((v-E)/v1) : 1
            #phi : meter**-2*second**-1
            #stimulus : 1
            #I = g*(S_O1+gam*S_O2)*fv*(v-E) : amp
            #'''
    
    """
    brian_phi_t = '''
            dS_C1/dt = Gr0*S_C2 + Gd1*S_O1 - Ga1*S_C1 : 1
            dS_I1/dt = Ga1*S_C1 - Go1*S_I1 : 1
            dS_O1/dt = Go1*S_I1 - (Gd1+Gf)*S_O1 + Gb*S_O2 : 1
            dS_O2/dt = Go2*S_I2 + Gf*S_O1 - (Gd2+Gb)*S_O2 : 1
            dS_I2/dt = Ga2*S_C2 - Go2*S_I2 : 1
            S_C2 = 1 - S_C1 - S_I1 - S_O1 - S_O2 - S_I2 : 1
            H_p = Theta*((phi(t)**p)/(phi(t)**p+phi_m**p)) : 1
            H_q = Theta*((phi(t)**q)/(phi(t)**q+phi_m**q)) : 1
            Ga1 = k1*H_p : second**-1
            Ga2 = k2*H_p : second**-1
            Gf = Gf0 + kf*H_q : second**-1
            Gb = Gb0 + kb*H_q : second**-1
            f_v = (1-exp(-(v-E)/v0))/((v-E)/v1) : 1
            f_phi = S_O1+gam*S_O2 : 1
            I = g0*f_phi*f_v*(v-E) : amp
            Theta = int(phi(t) > 0*phi(t)) : boolean (shared)
            '''
    """
    
    brian_phi_t = '''
            dC_1/dt = Gr0*C_2 + Gd1*O_1 - Ga1*C_1 : 1
            dI_1/dt = Ga1*C_1 - Go1*I_1 : 1
            dO_1/dt = Go1*I_1 - (Gd1+Gf)*O_1 + Gb*O_2 : 1
            dO_2/dt = Go2*I_2 + Gf*O_1 - (Gd2+Gb)*O_2 : 1
            dI_2/dt = Ga2*C_2 - Go2*I_2 : 1
            C_2 = 1 - C_1 - I_1 - O_1 - O_2 - I_2 : 1
            H_p = Theta*((phi(t)**p)/(phi(t)**p+phi_m**p)) : 1
            H_q = Theta*((phi(t)**q)/(phi(t)**q+phi_m**q)) : 1
            Ga1 = k1*H_p : second**-1
            Ga2 = k2*H_p : second**-1
            Gf = Gf0 + k_f*H_q : second**-1
            Gb = Gb0 + k_b*H_q : second**-1
            f_v = (1-exp(-(v-E)/v0))/((v-E)/v1) : 1
            f_phi = O_1+gam*O_2 : 1
            I = g0*f_phi*f_v*(v-E) : amp
            Theta = int(phi(t) > 0*phi(t)) : 1 (shared)
            '''
    
    def _calcGa1(self, phi):
        #return self.a10*(phi/self.phi0)
        return self.k1 * phi**self.p/(phi**self.p + self.phi_m**self.p)

    def _calcGf(self, phi):
        #return self.a30 + self.a31*np.log(1+(phi/self.phi0))
        return self.Gf0 + self.k_f * phi**self.q/(phi**self.q + self.phi_m**self.q)

    def _calcGb(self, phi):
        #return self.b20 + self.b21*np.log(1+(phi/self.phi0))
        return self.Gb0 + self.k_b * phi**self.q/(phi**self.q + self.phi_m**self.q)

    def _calcGa2(self, phi):
        #return self.b40*(phi/self.phi0)
        return self.k2 * phi**self.p/(phi**self.p + self.phi_m**self.p)

    def setLight(self, phi):
        #assert(phi >= 0)
        if phi < 0:
            phi = 0
        self.phi = phi
        self.Ga1 = self._calcGa1(phi)
        self.Gf = self._calcGf(phi)
        self.Gb = self._calcGb(phi)
        self.Ga2 = self._calcGa2(phi)
        if verbose > 1:
            self.dispRates()
        
    def dispRates(self):
        print("Transition rates (phi={:.3g}): O1 --[Gf]--> O2 = {}; O1 <--[Gb]-- O2 = {}".format(self.phi,self.Gf,self.Gb))
        print("                  ^O1      O2^")
        print("                   \        /")
        print("                  [Ga1]  [Ga2]")
        print("                     \    /")
        print("                     C1  C2")
        print("Transition rates [Ga1] = {}; [Ga2] = {}".format(self.Ga1,self.Ga2))
    
    def solveStates(self, s_0, t, phi_t=None):
        """Function describing the differential equations of the 6-state model to be solved by odeint"""
        if phi_t is not None:
            self.setLight(float(phi_t(t)))
        C1, I1, O1, O2, I2, C2 = s_0 # Unpack state vector
        #s1,s2,s3,s4,s5,s6 = s_0 # Split state vector into individual variables s1=s[0], s2=s[1], etc
        dC1dt = -self.Ga1*C1 + self.Gd1*O1 + self.Gr0*C2           # s1'
        dI1dt =  self.Ga1*C1 - self.Go1*I1                        # s2'
        dO1dt =  self.Go1*I1 - (self.Gd1+self.Gf)*O1 + self.Gb*O2 # s3'
        dO2dt =  self.Gf*O1 - (self.Gb+self.Gd2)*O2 + self.Go2*I2 # s4'
        dI2dt = -self.Go2*I2 + self.Ga2*C2                        # s5'
        dC2dt =  self.Gd2*O2 - (self.Ga2+self.Gr0)*C2              # s6'
        #d5 = - (f0+f1+f2+f3+f4)
        #dr0 = -2*pi*f*sin(2*pi*f*t)*C(1+cos(2*pi*f*t))      # d/dt (A(1+cos(2*pi*f*t)))
        return np.array([ dC1dt, dI1dt, dO1dt, dO2dt, dI2dt, dC2dt ])

    def jacobian(self, s_0, t, phi_t=None):
        return np.array([[-self.Ga1, 0, self.Gd1, 0, 0, self.Gr0],
                         [self.Ga1, -self.Go1, 0, 0, 0, 0],
                         [0, self.Go1, -(self.Gd1+self.Gf), self.Gb, 0, 0],
                         [0, 0, self.Gf, -(self.Gb+self.Gd2), self.Go2, 0],
                         [0, 0, 0, 0, -self.Go2, self.Ga2],
                         [0, 0, 0, self.Gd2, 0, -(self.Ga2+self.Gr0)]])
    
    '''
    def calcI(self, V, states=None):#, gam=None, E=None, g=None): # Change to (V, psi)?
        """Takes Voltage [mV] and state variables O1 and O2 to calculate current [nA]
        By convention, positive ions entering the cell --> negative current (e.g. Na^+ influx). 
        Conversely, Positive ions leaving (or negative ions entering) the cell --> positive current (e.g. Cl^- in or K^+ out). """
        #if g is None:
        g0 = self.g0
        if states is None:
            states = self.states
        O1 = states[:,2] # O1
        O2 = states[:,3] # O2
        #if gam is None:
        gam = self.gam
        #if E is None:
        E = self.E
        psi = O1 + (gam * O2) # Dimensionless
        
        g_RhO = g0 * psi * self.calcfV(V) #* fV # self.gbar * self.A # Conductance (pS * um^-2)
        I_RhO =  g_RhO * (V - E) # Photocurrent: (pS * mV)
        return I_RhO * (1e-6) # 10^-12 * 10^-3 * 10^-6 (nA)
    '''
    
    ##############################################################    
    # def rectifier(V): ##### Redundant
        # if self.v0 == 0:
            # warnings.warn("f(V) undefined for v0 = 0")
        # try:
            # fV = (self.v1/(V-self.E))*(1-np.exp(-(V-self.E)/self.v0)) # Dimensionless
        # except ZeroDivisionError:
            # pass
        # fV = (self.v1/(V-self.E))*(1-np.exp(-(V-self.E)/self.v0)) # Dimensionless
        # if np.isscalar(fV):
            # if (V == self.E):
                # fV = self.v1/self.v0
        # else: #type(fV) in (tuple, list, array)
            # fV[np.isnan(fV)] = self.v1/self.v0 # Fix the error when dividing by zero

        # return fV
    
    # def equalFloats(x,y,eps=1e-6): # Use numpy.allclose(a, b, rtol=1e-05, atol=1e-08)
        # diff = np.abs(x-y)
        # if (x == y): # Catch infinities
            # return True
        # elif (x == 0 or y == 0 or diff < floatmin): # Either one number is 0 or both are very close
            # return diff < (eps * floatmin)
        # else: # Use relative error
            # return diff / (np.abs(x) + np.abs(y)) < eps
    #############################################################
        
    def calcSteadyState(self, phi): # implicitly depends on phi0
        self.setLight(phi)
        Ga1 = self.Ga1
        Go1 = self.Go1
        Gf = self.Gf
        Gd2 = self.Gd2
        Gr0 = self.Gr0
        Gd1 = self.Gd1
        Gb = self.Gb
        Go2 = self.Go2
        Ga2 = self.Ga2
        denom6 = (Ga1*Go1*(Gf*(Go2*(Ga2+Gd2)+Gd2*Ga2)+Gb*Go2*Ga2)+Gd1*(Go1*Gb*Go2*Ga2+Ga1*Gb*Go2*Ga2+Gr0*(Go1*(Gb*Go2+Gd2*Go2)+Ga1*(Gb*Go2+Gd2*Go2)))+Gr0*(Ga1*(Go1*(Gb*Go2+Gd2*Go2+Gf*Go2)+Gf*Gd2*Go2)+Go1*Gf*Gd2*Go2))
        C1s = (Gd1*(Go1*Gb*Go2*Ga2 + Go1*Gr0*(Gb*Go2 + Gd2*Go2)) + Go1*Gf*Gd2*Gr0*Go2)/denom6
        I1s = (Gd1*(Ga1*Gb*Go2*Ga2 + Ga1*Gr0*(Gb*Go2 + Gd2*Go2)) + Ga1*Gf*Gd2*Gr0*Go2)/denom6
        O1s = (Ga1*Go1*Gb*Go2*Ga2 + Ga1*Go1*Gr0*(Gb*Go2 + Gd2*Go2))/denom6
        O2s = (Ga1*Go1*Gf*Go2*Ga2 + Ga1*Go1*Gf*Gr0*Go2)/denom6
        I2s = (Ga1*Go1*Gf*Gd2*Ga2)/denom6
        C2s = (Ga1*Go1*Gf*Gd2*Go2)/denom6
        self.steadyStates = np.array([C1s, I1s, O1s, O2s, I2s, C2s])
        return self.steadyStates #np.array([C1s, I1s, O1s, O2s, I2s, C2s])
    
    def calcfphi(self, states=None):#, gam=None):
        """Function to calculate the conductance scalar from the photocycle"""
        if states is None:
            states = self.states
        C1, I1, O1, O2, I2, C2 = states.T
        #if gam is None:
        gam = self.gam
        return O1 + gam * O2
        
    def calcSoln(self, t, s0=[1,0,0,0,0,0]):
        raise NotImplementedError(self.nStates)
        

models = OrderedDict([('3', RhO_3states), ('4', RhO_4states), ('6', RhO_6states), (3, RhO_3states), (4, RhO_4states), (6, RhO_6states)])

def selectModel(nStates):
    """Model selection function"""
    if int(nStates) == 3 or nStates == 'three':
        return RhO_3states() #(E)
    elif int(nStates) == 4 or nStates == 'four':
        return RhO_4states() #(E,gam,phi0)
    elif int(nStates) == 6 or nStates == 'six':
        return RhO_6states() #(E,gam,phi0,A)
    else:
        print("Error in selecting model - please choose from 3, 4 or 6 states")
        raise NotImplementedError(nStates)
        
