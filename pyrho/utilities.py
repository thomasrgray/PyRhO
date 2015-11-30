import numpy as np
import matplotlib.pyplot as plt
import warnings
import pickle

import os
import shutil # for file copying
import subprocess # for running system commands
import copy

from pyrho.config import * #verbose, dDir, fDir

### Physical constants
h = 6.6260695729e-34    # Planck's constant (Js)
c = 2.99792458e8        # Speed of light    (m*s^-1)
#NA = 6.0221413e23      # Avogadro's Number (mol^-1)


# http://preshing.com/20110924/timing-your-code-using-pythons-with-statement/
#import time
#with Timer() as t:
#   run code...
# print('Execution took ', t)

class Timer:
    interval = 0
    
    def __enter__(self):
        self.start = wallTime() #time.clock()
        return self

    def __exit__(self, *args):
        self.end = wallTime() #time.clock()
        self.interval = self.end - self.start
    
    def __str__(self):
        return '{:.3g}s'.format(self.interval)


def printParams(params):
    vd = params.valuesdict()
    report = '------------------------\n'
    report += '       Parameters\n'
    report += '------------------------\n'
    for k,v in vd.items():
        if isinstance(v, (int, float, complex)):
            report += '{:>7} = {:8.3g}\n'.format(k,v)
        else: # Check for bool?
            report += '{:>7} = {:8}\n'.format(k,str(v))
    report += '========================\n'
    print(report)
    
def compareParams(origParams, newParams):
    ovd = origParams.valuesdict()
    nvd = newParams.valuesdict()
    report  = '--------------------------------------------\n'
    report += '          Original        New    Change     \n'
    report += '--------------------------------------------\n'
    for k,nv in nvd.items():
        ov = ovd[k]
        if isinstance(nv, (int, float, complex)):
            if ov > 1e-4: #ov != 0:
                report += '{:>7} = {:8.3g} --> {:8.3g} ({:+.3g}%)\n'.format(k,ov,nv,(nv-ov)*100/ov)
            else:
                report += '{:>7} = {:8.3g} --> {:8.3g} (Abs: {:+.3g})\n'.format(k,ov,nv,nv-ov)
        else: # Check for bool?
            report += '{:>7} = {:8}\n'.format(k,str(nv))
    report += '============================================\n'
    print(report)
    
def texIt(texString):
    """Function to add '$' signs around a (La)TeX string"""
    from string import Template
    texTemplate = Template('${content}$')
    return texTemplate.substitute(content=texString)
    
def saveData(data, pkl, path=None):
    # if pkl is None:
        # pkl = data.__name__
    if path is None:
        path = dDir
    pklFile = os.path.join(path, pkl+".pkl")
    with open(pklFile, 'wb') as fh:
        pickle.dump(data, fh)
    if verbose > 0: #config.verbose?!
        print("Data saved to disk: {}".format(pklFile))
    return pklFile
    
def loadData(pkl, path=None):
    if pkl.lower().endswith('.pkl'):
        pklFile = pkl
    else:
        pklFile = pkl + '.pkl'
    if path is None:
        if os.path.isfile(pklFile):
            pass
        else:
            pklFile = os.path.join(dDir, pklFile)
    else:
        pklFile = os.path.join(path, pklFile)
    with open(pklFile, 'rb') as fh:
        dataSet = pickle.load(fh)
    return dataSet
    
def getExt(vector, ext='max'):
    if ext == 'max':
        mVal = max(vector)
    elif ext == 'min':
        mVal = min(vector)
    mInd = np.searchsorted(vector, mVal)
    return mVal, mInd
    
def getIndex(valList, val):
    """Return the index of val in valList.
    This handles lists containing None"""
    
    # valList types: list, array, number
    #   +/- None
    # val types: list, array, number
    #   +/- None
    
    # Vs=[-100,-70,-40,-10]
    # V = -70
    # np.where(np.isclose(Vs,V))[0] # Array of indices
    
    # locList = copy.copy(valList)
    # if isinstance(valList, (list, tuple)):
        # try:
            # ind = valList.index(val)
        # except:
            # pass
    # elif isinstance(valList, (np.ndarray, np.generic)):
        # try:
            # cl = np.isclose(valList, val)
            # ind = np.searchsorted(cl, True)
            ###ind = np.searchsorted(cl, True, equal_nan=True)
        # except:
            # pass
        # else:
            # locList = valList.tolist()
    # elif isinstance(valList, (int, long, float, complex)):
        # locList = list([copy.copy(valList)])
    # else:
        # raise TypeError("Value list must be a list, array or number")
    
    
    
    locList = list(copy.copy(valList))
    if val is None:
        try:
            ind = locList.index(None)
        except ValueError:
            raise
    else:
        try:
            iNone = locList.index(None)
            locList[iNone] = np.nan
        except:
            pass
        cl = list(np.isclose(locList, val))
        try:
            ind = cl.index(True)
        except ValueError:
            ind = None
    return ind
    


def calcV1(E, v0):
    """Since f(V=-70):= 1, if v0 or E are changed, v1 must be recalculated to rescale correctly for simulations"""
    return (70+E)/(np.exp((70+E)/v0)-1)
    #return (-70-E)/(1-np.exp(-(-70-E)/v0))

'''
    == A few notes about colour ==

    Color   Wavelength(nm) Frequency(THz)
    Red     620-750        484-400
    Orange  590-620        508-484
    Yellow  570-590        526-508
    Green   495-570        606-526
    Blue    450-495        668-606
    Violet  380-450        789-668

    f is frequency (cycles per second)
    l (lambda) is wavelength (meters per cycle)
    e is energy (Joules)
    h (Plank's constant) = 6.6260695729 x 10^-34 Joule*seconds
                         = 6.6260695729 x 10^-34 m^2*kg/seconds
    c = 299792458 meters per second
    f = c/l
    l = c/f
    e = h*f
    e = c*h/l

    List of peak frequency responses for each type of 
    photoreceptor cell in the human eye:
        S cone: 437 nm
        M cone: 533 nm
        L cone: 564 nm
        rod:    550 nm in bright daylight, 498 nm when dark adapted. 
                Rods adapt to low light conditions by becoming more sensitive.
                Peak frequency response shifts to 498 nm.

'''


def lam2rgb(wav, gamma=0.8, output='norm'):
    """This converts a given wavelength of light to an 
    approximate RGB colour value with edge attenuation. 
    The wavelength must be given in nanometres in the 
    range from 380 nm - 750 nm (789 THz - 400 THz).
    
    Adapted from: http://www.noah.org/wiki/Wavelength_to_RGB_in_Python
    Based on code by Dan Bruton
    http://www.physics.sfasu.edu/astro/color/spectra.html
    """
    
    
    wav = float(wav)
    if wav >= 380 and wav < 440:
        attenuation = 0.3 + 0.7 * (wav - 380) / (440 - 380)
        R = ((-(wav - 440) / (440 - 380)) * attenuation) ** gamma
        G = 0.0
        B = (1.0 * attenuation) ** gamma
    elif wav >= 440 and wav < 490:
        R = 0.0
        G = ((wav - 440) / (490 - 440)) ** gamma
        B = 1.0
    elif wav >= 490 and wav < 510:
        R = 0.0
        G = 1.0
        B = (-(wav - 510) / (510 - 490)) ** gamma
    elif wav >= 510 and wav < 580:
        R = ((wav - 510) / (580 - 510)) ** gamma
        G = 1.0
        B = 0.0
    elif wav >= 580 and wav < 645:
        R = 1.0
        G = (-(wav - 645) / (645 - 580)) ** gamma
        B = 0.0
    elif wav >= 645 and wav <= 750:
        attenuation = 0.3 + 0.7 * (750 - wav) / (750 - 645)
        R = (1.0 * attenuation) ** gamma
        G = 0.0
        B = 0.0
    else: # Outside the visible spectrum
        R = 0.0
        G = 0.0
        B = 0.0
    
    if output == 'norm':
        return (R,G,B)
    elif output == 'hex':
        R *= 255
        R = max(0, min(round(R), 255))
        G *= 255
        G = max(0, min(round(G), 255))
        B *= 255
        B = max(0, min(round(B), 255))
        #return (int(R), int(G), int(B)) # int() truncates towards 0
        return "#{0:02x}{1:02x}{2:02x}".format(R,G,B), (R,G,B)


### Model functions ###

def irrad2flux(E,lam=470):   # E2phi
    """Converts irradiance [mW * mm^-2] and wavelength (default: 470) [nm] to flux [photons * s^-1 * mm^-2]"""
    Ep = 1e12 * h * c/lam    # Energy per photon [mJ] (using lambda in [nm])
    return E/Ep              # Photon flux (phi) scaled to [photons * s^-1 * mm^-2]


def flux2irrad(phi,lam=470):
    """Converts flux [photons * s^-1 * mm^-2] and wavelength (default: 470) [nm] to irradiance [mW * mm^-2]"""
    Ep = 1e12 * h * c/lam    # Energy per photon [mJ] (using lambda in [nm])
    return phi * Ep          # Irradiance (E) scaled to [mW * mm^-2]


def calcgbar(Ip,Vclamp,A):
    # Unused
    """Function to calculate a lower bound on the cell's maximum conductance from its peak current
    Ip      :=  Peak current [nA]
    Vclamp  :=  Clamp Voltage [mV]
    A       :=  Cell surface area [um^2]
    return gbar [pS/um^2]"""
    Gmax = Ip/Vclamp  # Maximum conductance for the whole cell
    gbar = Gmax/A     # Maximum conductance pS / um^2
    return gbar * (1e6) # 1e-12 S / (1e-6 m)^2 = (1e-6)*(1e-9 A / 1e-3 V)/(1e-6 m)^2 # Check the conversion factor

    
    
def times2cycles(times, totT):       # REVISE to handle negative delay times
    """Input    times:= [t_on,t_off], t_tot
       Output   cycles:= [onD,offD], delD"""
    times = np.array(times, copy=True)
    nPulses = times.shape[0]
    assert(times.shape[1] <= 2)
    delD = times[0,0] # This assumes that the times have not been shifted
    onDs = [row[1]-row[0] for row in times] # pulses[:,1] - pulses[:,0]   # Pulse Durations
    offDs = np.append(times[1:,0],totT) - times[:,1]
    cycles = np.vstack((onDs,offDs)).transpose()
    return (cycles, delD)

    
def cycles2times(cycles, delD):
    """Function to convert pulse cycles to times. 
        Input    cycles:= [onD,offD], delD
        Output   times:= [t_on,t_off], totT"""
    
    ### Generalise to delDs c.f. recovery
    cycles = np.array(cycles)
    nPulses = cycles.shape[0]
    assert(cycles.shape[1] <= 2)
    times = np.zeros((nPulses, 2)) #[delD,delD+cycles[row,0] for row in pulses]
    lapsed = delD
    for p in range(nPulses):
        times[p,0] = lapsed
        times[p,1] = lapsed+cycles[p,0]
        lapsed += sum(cycles[p,:])
    return (times, lapsed)

    
def plotLight(times, ax=None, light='shade', lam=470, alpha=0.2): #=plt.gcf()
    """Function to plot light pulse(s)
    times   = [[t_on, t_off]...]
    ax      = Axes to plot on (default: gca()
    light   = Representation type: {'shade', 'borders', 'greyscale', 'hatch', 'spectral'}. Default: 'shade'
    lam     = Wavelength [nm] (default: 470)
    alpha   = Transparency (default: 0.2)"""
    
    ### Change plt.axvspan to ax.axvspan etc. 
    if ax==None:
        ax=plt.gca()
    else:
        plt.sca(ax)
    nPulses = times.shape[0]
    if light == 'shade':
        for p in range(nPulses):
            ax.axvspan(times[p][0],times[p][1],facecolor='y',alpha=alpha)    # plt.
    elif light == 'borders': 
        for p in range(0, nPulses): ############################ Move to plotLight
            ax.axvline(x=times[p][0],linestyle='--',color='k')
            ax.axvline(x=times[p][1],linestyle='--',color='k')
    elif light == 'greyscale':
        for p in range(nPulses):
            # Set background to grey and illumination to white
            ax.set_axis_bgcolor('0.4') #'0.3'
            ax.axvspan(times[p][0],times[p][1],facecolor='w')#,alpha=alpha)  
    elif light == 'hatch':
        for p in range(nPulses):
            ax.axvspan(times[p][0],times[p][1],hatch='/') #'*'
    elif light == 'spectral':
        # Plot the colour corresponding to the wavelength
        if 380 <= lam <= 750:
            rgb = lam2rgb(lam)
            for p in range(0, nPulses): 
                ax.axvspan(times[p][0],times[p][1],facecolor=rgb,alpha=alpha)
        else: # Light is not in the visible spectrum - plot borders instead
            for p in range(0, nPulses): 
                ax.axvline(x=times[p][0],linestyle='--',color='k')
                ax.axvline(x=times[p][1],linestyle='--',color='k')
                ax.axvspan(times[p][0],times[p][1],hatch='/') #'*'
    elif light == 'None' or light == None:
        pass
    else:
        warnings.warn('Warning: Unrecognised light representation: {}!'.format(light))
    return
    
    
def round_sig(x, sig=3):
    """Round a float to n significant digits (default is 3). """
    if abs(x) == 0 or np.isinf(x) or np.isnan(x):
        return x
    else:
        return round(x, sig-int(np.floor(np.log10(abs(x))))-1)


# def calcIssfromfV(V,v0,v1,E):#,G): # Added E as another parameter to fit # ==> Fv() := fv()*(V-E)
    # ##[s1s, s2s, s3s, s4s, s5s, s6s] = RhO.calcSteadyState(RhO.phiOn)
    # ##psi = s3s + (RhO.gam * s4s) # Dimensionless
    
    # #E = RhO.E
    # if type(V) != np.ndarray:
        # V = np.array(V)
    # fV = (1-np.exp(-(V-E)/v0))/((V-E)/v1) # Dimensionless #fV = abs((1 - exp(-v/v0))/v1) # Prevent signs cancelling
    # fV[np.isnan(fV)] = v1/v0 # Fix the error when dividing by zero
    # ##psi = RhO.calcPsi(RhO.steadyStates) ### This is not necessary for fitting!!!
    # ##g_RhO = RhO.gbar * psi * fV # Conductance (pS * mu m^-2)
    # ##I_ss = RhO.A * g_RhO * (V - E) # Photocurrent: (pS * mV)
    # #I_ss = G * fV * (V-E)
    # ##return I_ss * (1e-6) # 10^-12 * 10^-3 * 10^-6 (nA)
    # return fV * (V - E)
    
# def fitfV(Vs, Iss, curveFunc, p0, RhO, fig=None):#, eqString): =plt.gcf()
    # if fig==None:
        # fig=plt.gcf()
    # markerSize=40
    # eqString = r'$f(V) = \frac{{{:.3}}}{{V-{:+.2f}}} \cdot \left[1-\exp\left({{-\frac{{V-{:+.2f}}}{{{:.3}}}}}\right)\right]$'
    # psi = RhO.calcPsi(RhO.steadyStates)
    # #sf = RhO.A * RhO.gbar * psi * 1e-6 # Six-state only
    # sf = RhO.g * psi * 1e-6 
    # fVs = np.asarray(Iss)/sf # np.asarray is not needed for the six-state model!!!
    # popt, pcov = curve_fit(curveFunc, Vs, fVs, p0=p0) # (curveFunc, Vs, Iss, p0=p0)
    # pFit = [round_sig(p,3) for p in popt]
    # peakEq = eqString.format(pFit[0],pFit[2],pFit[2],pFit[1])
    
    # Vrange = max(Vs)-min(Vs)
    # xfit=np.linspace(min(Vs),max(Vs),Vrange/.1) #Prot.dt
    # yfit=curveFunc(xfit,*popt)*sf
    
    # #peakEq = eqString.format(*[round_sig(p,3) for p in popt])
    
    # fig.plot(xfit,yfit)#,label=peakEq)#,linestyle=':', color='#aaaaaa')
    # #col, = getLineProps(Prot, 0, 0, 0) #Prot, run, vInd, phiInd
    # #plt.plot(Vs,Iss,linestyle='',marker='x',color=col)
    # fig.scatter(Vs,Iss,marker='x',color=colours,s=markerSize)#,linestyle=''
    
    # # x = 1 #0.8*max(Vs)
    # # y = 1.2*yfit[-1]#max(IssVals[run][phiInd][:])
    # # plt.text(-0.8*min(Vs),y,peakEq,ha='right',va='bottom',fontsize=eqSize)#,transform=ax.transAxes)
    
    # if verbose:
        # print(peakEq)
    # return popt, pcov, peakEq




def expDecay(t, a, b, c):
    return a * np.exp(-t/b) + c

def biExpDecay(t, a1, tau1, a2, tau2, I_ss):
    return a1 * np.exp(-t/tau1) + a2 * np.exp(-t/tau2) + I_ss

def biExpSum(t, a1, tau1, a2, tau2, I_ss):
    return a0 + a1*(1-np.exp(-t/tau_act)) + a2*np.exp(-t/tau_deact)
    
# def fitPeaks(t_peaks, I_peaks, curveFunc, p0, eqString, fig=None):
    
    # shift = t_peaks[0] # ~ delD
# #     if protocol == 'recovery':
# #         plt.ylim(ax.get_ylim()) # Prevent automatic rescaling of y-axis
    # popt, pcov = curve_fit(curveFunc, t_peaks-shift, I_peaks, p0=p0) #Needs ball-park guesses (0.3, 125, 0.5)
    # peakEq = eqString.format(*[round_sig(p,3) for p in popt]) # *popt rounded to 3s.f.
    
    # if fig:
        # plt.figure(fig.number) # Select figure
# #     ext = 10 # Extend for ext ms either side
# #     xspan = t_peaks[-1] - t_peaks[0] + 2*ext 
# #     xfit=np.linspace(t_peaks[0]-ext-shift,t_peaks[-1]+ext-shift,xspan/dt)
        # plt.plot(t_peaks, I_peaks, linestyle='', color='r', marker='*')
        # xfit=np.linspace(-shift,Prot.totT-shift,Prot.totT/Prot.dt) #totT
        # yfit=curveFunc(xfit,*popt)
        
        # plt.plot(xfit+shift,yfit,linestyle=':',color='#aaaaaa')#,label="$v={:+} \mathrm{{mV}}$, $\phi={:.3g}$".format(V,phiOn))
        # #ylower = copysign(1.0,I_peaks.min())*ceil(abs((I_peaks.min()*10**ceil(abs(log10(abs(I_peaks.min())))))))/10**ceil(abs(log10(abs(I_peaks.min()))))
        # #yupper = copysign(1.0,I_peaks.max())*ceil(abs((I_peaks.max()*10**ceil(abs(log10(abs(I_peaks.max())))))))/10**ceil(abs(log10(abs(I_peaks.max()))))
    # #     if (len(Vs) == 1) and (len(phis) == 1) and (nRuns == 1):
    # #         x, y = 0.8, 0.9
    # #     else:
        # x = 0.8
        # y = yfit[-1] #popt[2]
        
        # plt.text(x*Prot.totT,y,peakEq,ha='center',va='bottom',fontsize=eqSize) #, transform=ax.transAxes)
    
    # print(peakEq)
    # if verbose > 1:
        # print("Parameters: {}".format(popt))
        # if type(pcov) in (tuple, list):
            # print("$\sigma$: {}".format(np.sqrt(pcov.diagonal())))
        # else:
            # print("Covariance: {}".format(pcov))
    # return popt, pcov, peakEq




def findPeaks(I_phi,startInd=0,extOrder=5): # Revise this to take care of V<>E 
# findPeaks(I_phi,minmax,startInd=0,extOrder=5)
    from scipy.signal import argrelextrema #for argrelextrema
    
    if verbose > 1:
        print("findPeaks(): extOrder = ",extOrder)
    if np.isnan(I_phi).all() or len(I_phi)==0: # Not necessary
        warning.warn("Warning: No photocurrent for run[{}]phi[{}]v[{}]!".format(run,phiInd,vInd))
        #print("Warning: No photocurrent for run[{}]phi[{}]v[{}]!".format(run,phiInd,vInd))
        return []
    else:
        if abs(min(I_phi)) > abs(max(I_phi)): # Find Minima
            minmax = np.less #Ipmax = min(photocurrent.I_phi)
        else:       # Find Maxima
            minmax = np.greater #Ipmax = max(photocurrent.I_phi)
#         if (extOrder < 1):
#             if (V < E): # Find Minima
#                 Ip = min(I_phi)
#                 peakInds = [np.argmin(I_phi) + startInd]
#             else:       # Find Maxima
#                 Ip = max(I_phi)
#                 peakInds = [np.argmax(I_phi) + startInd]
#         else:
        # if (V < E): # Find Minima
            # peakInds = argrelextrema(I_phi[startInd:], np.less, order=extOrder)
        # else:       # Find Maxima
            # peakInds = argrelextrema(I_phi[startInd:], np.greater, order=extOrder)
        peakInds = argrelextrema(I_phi[startInd:], minmax, order=extOrder)
        peakInds = peakInds[0] + startInd # Remove tuple and transform into original co-ordinates
        peakInds = peakInds.astype(int)
#         Ip = I_phi[peakInds]

        ### Alternatively loop over pulses taking the min() or max() within each region

        if peakInds.any() and verbose > 1:
            print(peakInds)
            print("I[p-2]={}; I[p-1]={}; I[p]={}; I[p+1]={}; I[p+2]={};".format(*I_phi[peakInds-2:peakInds+3]))
        return peakInds #, Ip        

        
def findPlateauCurrent(I_phi,p=0.1): ### c.f. findPlateaus() in loadData.py
    """Trim the off-phase of I_phi. Optionally pass the proportion of data for the averaging window, p. """
    # Move a sliding window over the data and look for abs(dI/dt) < eps
    # Take the mean of the last p*t ms before t_off
    # Take the mean of the last n ms before t_off
    #onEndInd = np.searchsorted(t,onD+delD,side="left")
    windowInd = int(round(p*len(I_phi))) #np.searchsorted(t,t[onEndInd]-100,side="left") # Generalise
    I_ss = np.mean(I_phi[-windowInd:]) #:onEndInd+1
    # Fit an exponential from the t_peak to t_off
    # searchSlice = slice(peakInds[0], offInd+1)
    # popt = fitPeaks(t[peakInds[0]:offInd+1], I_phi[peakInds[0]:offInd+1], expDecay, p0inact, '$I_{{inact}} = {:.3}e^{{-t/{:g}}} {:+.3}$','')
    # Iss = popt[2]
    
    # Alternatively use a gradient-based approach
    #if abs(np.gradient(I_phi)) < tol:
    
    return I_ss
