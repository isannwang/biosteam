# -*- coding: utf-8 -*-
"""
Created on Sat Sep  1 17:35:28 2018

@author: yoelr
"""
from biosteam import np, Stream, Unit
from biosteam.meta_classes import metaFinal

__all__ = ['MassBalance']

# %% Mass Balance Unit

class MassBalance(Unit, metaclass=metaFinal):
    """Create a Unit object that changes net input flow rates to satisfy output flow rates. This calculation is based on mass balance equations for specified species. 

    **Parameters**

        **species**: tuple[str] Species that will be used to solve mass balance linear equations. The number of species must be same as the number of input streams varied.

        **streams**: tuple[int] Indices of input streams that can vary in net flow rate

        **exact**: [bool] True if exact flow rate solution is required for the specified species.

        **balance**: [str] Should be one of the follwing
                  * 'flow' - To satisfy output flow rates
                  * 'fraction' - To satisfy net output molar fractions

    .. Note::

        This is an end-of-the-line/final class that cannot be inherited.

    """
    _N_outs = 0
    kwargs = {'species': None,
              'streams': None,
              'exact': True,
              'balance': 'flow'}

    def setup(self):
        exact = self.kwargs['exact']
        balance = self.kwargs['balance']
        self._cached = cached = {}
        # Make sure balance type is valid
        if balance not in ('flow', 'fraction'):
            raise ValueError(
                "Balance type must be one of the following: 'flow', 'fraction'")

        # Cach correct solver and make sure linear system of equations is square to achieve exact solution
        if exact:
            solver = np.linalg.solve
            specie_IDs = self.kwargs['species']
            sID, s_index = len(specie_IDs), len(self.kwargs['streams'])
            if sID != s_index:
                raise ValueError(
                    f"Length of species ({sID}) must be equal to the length of streams_index ({s_index}) when exact solution is needed.")
        else:
            solver = np.linalg.lstsq

        # Cach indices for species and solver
        sp_index = Stream._ID_index
        cached['bal_index'] = [sp_index[specie] for specie in specie_IDs]
        cached['linalg_solver'] = solver

    def run(self):
        """Solve mass balance by iteration."""
        # SOLVING BY ITERATION TAKES 15 LOOPS FOR 2 STREAMS
        # SOLVING BY LEAST-SQUARES TAKES 40 LOOPS
        kwargs = self.kwargs
        cached= self._cached
        stream_index = kwargs['streams']
        balance = kwargs['balance']
        solver = cached['linalg_solver']

        # Set up constant and variable streams
        vary = []  # Streams to vary in mass balance
        constant = []  # Constant streams
        for i in range(len(self.ins)):
            if i in stream_index:
                vary.append(self.ins[i])
            else:
                constant.append(self.ins[i])

        # Species indices used in mass balace
        index = cached['bal_index']

        if balance == 'flow':
            # Perform the following calculation: Ax = b = f - g
            # Where:
            #    A = flow rate array
            #    x = factors
            #    b = target flow rates
            #    f = output flow rates
            #    g = constant input flow rates

            # Solve linear equations for mass balance
            A = np.array([s.mol for s in vary]).transpose()[index, :]
            f = self._mol_out[index]
            g = sum([s.mol[index] for s in constant])
            b = f - g
            x = solver(A, b)

            # Set flow rates for input streams
            for factor, s in zip(x, vary):
                s.mol = s.mol * factor

        elif balance == 'fraction':
            # Perform the following calculation:
            # Ax = b
            #    = sum( A_ * x_guess + g_ )f - g
            #    = A_ * x_guess * f - O
            # O  = sum(g_)*f - g
            # Where:
            # A_ is flow array for all species
            # g_ is constant flows for all species
            # Same variable definitions as in 'flow'

            # Set all variables
            A_ = np.array([s.mol for s in vary]).transpose()
            A = np.array([s.mol for s in vary]).transpose()[index, :]
            f = self._molfrac_out[index]
            g_ = sum([s.mol for s in constant])
            g = g_[index]
            O = sum(g_) * f - g

            # Solve by iteration
            x_guess = np.ones_like(index)
            not_converged = True
            while not_converged:
                # Solve linear equations for mass balance
                i += 1
                b = (A_ * x_guess).sum()*f + O
                x_new = solver(A, b)
                not_converged = sum(((x_new - x_guess)/x_new)**2) > 0.00001
                x_guess = x_new

            # Set flow rates for input streams
            for factor, s in zip(x_new, vary):
                s.mol = s.mol * factor

    _simple_run = run

    # Setting input and output streams do not change sources or sinks
    @property
    def ins(self):
        """[:] Input streams"""
        return self._ins

    @ins.setter
    def ins(self, streams):
        self._ins = list(streams)

    @property
    def outs(self):
        """[:] Output streams"""
        return self._outs

    @outs.setter
    def outs(self, streams):
        self._outs = list(streams)


# %% Energy Balance Unit

class EnergyBalance(Unit, metaclass=metaFinal):
    """Create a Unit object that changes a stream temperature, flow rate, or vapor fraction to satisfy energy balance.

    **Parameters**

        **index:** [int] Index of stream that can vary in temperature, flow rate, or vapor fraction.
        
        **Type:** [str] Should be one of the following
            * 'T': Vary temperature of output stream
            * 'V': Vary vapor fraction of output stream
            * 'F': 'Vary flow rate of input/output stream
        
        **Qin:** *[float]* Additional energy input.

    .. Note::

        This is an end-of-the-line/final class that cannot be inherited.

    """
    _Graphics = MassBalance._Graphics
    
    def run(self):
        # Get arguments
        ins = self.ins.copy()
        outs = self.outs.copy()
        kwargs = self.kwargs
        index = kwargs['index']
        Type = kwargs['Type']
        Q_in = kwargs['Qin']
        
        # Pop out required streams
        if Type == 'F':
            s_in = ins.pop(index)
            s_out = outs.pop(index)
        else:
            s = outs.pop(index)
        
        # Find required enthalpy
        H_in = sum(i.H for i in ins) + Q_in
        H_out = sum(o.H for o in outs)
        H_s = H_out - H_in
        
        # Set enthalpy
        if Type == 'T':
            s.H = -H_s
        elif Type == 'V':
            s.enable_phases()
            s.VLE(Qin=s.H - H_s)
        elif Type == 'F':
            s.mol *= (s_out.H - s_in.H)/H_s
        else:
            raise ValueError(f"Type must be 'T', 'V' or 'F', not '{Type}'")
            
        
        