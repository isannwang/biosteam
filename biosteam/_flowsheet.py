# -*- coding: utf-8 -*-
# BioSTEAM: The Biorefinery Simulation and Techno-Economic Analysis Modules
# Copyright (C) 2020-2021, Yoel Cortes-Pena <yoelcortes@gmail.com>
# 
# This module is under the UIUC open-source license. See 
# github.com/BioSTEAMDevelopmentGroup/biosteam/blob/master/LICENSE.txt
# for license details.
"""
As BioSTEAM objects are created, they are automatically registered. The `main_flowsheet` object allows the user to find any Unit, Stream or System instance.  When `main_flowsheet` is called, it simply looks up the item and returns it. 
"""
from thermosteam.utils import Registry
from thermosteam import Stream
from biosteam.utils import feeds_from_units, sort_feeds_big_to_small
from ._unit import Unit
from ._system import System
from ._network import Network

__all__ = ('main_flowsheet', 'Flowsheet')


# %% Flowsheet search      

class Flowsheets:
    __getattribute__ = __getitem__ = object.__getattribute__
    
    def __setattr__(self, key, value):
        raise TypeError(f"'{type(self).__name__}' object does not support attribute assignment")
    __setitem__ = __setattr__
    
    def __iter__(self):
        yield from self.__dict__.values()
    
    def __delattr__(self, key):
        if key == main_flowsheet.ID:
            raise AttributeError('cannot delete main flowsheet')
        else:
            super().__delattr__(key)
    
    def __repr__(self):
        return 'Register:\n ' + '\n '.join([repr(i) for i in self])
    
    
class Flowsheet:
    """
    Create a Flowsheet object which stores references to all stream, unit,
    and system objects. For a tutorial on flowsheets, visit
    :doc:`tutorial/Managing_flowsheets`.
	
    """
    
    line = "Flowsheet"
    
    #: [Register] All flowsheets.
    flowsheet = Flowsheets()
    
    def __new__(cls, ID):        
        self = super().__new__(cls)
        
        #: [Register] Contains all System objects as attributes.
        self.system = Registry()
        
        #: [Register] Contains all Unit objects as attributes.
        self.unit = Registry()
        
        #: [Register] Contains all Stream objects as attributes.
        self.stream = Registry()
        
        #: [str] ID of flowsheet.
        self._ID = ID
        self.flowsheet.__dict__[ID] = self
        return self
    
    def __reduce__(self):
        return self.from_registries, self.registries
    
    def __setattr__(self, key, value):
        if hasattr(self, '_ID'):
            raise TypeError(f"'{type(self).__name__}' object does not support attribute assignment")
        else:
            super().__setattr__(key, value)
    
    @property
    def ID(self):
        return self._ID
    
    @classmethod
    def from_registries(cls, stream, unit, system):
        flowsheet = super().__new__(cls)
        flowsheet.stream = stream
        flowsheet.unit = unit
        flowsheet.system = system
        return flowsheet
    
    @property
    def registries(self):
        return (self.stream, self.unit, self.system)
    
    def clear(self):
        for registry in self.registries: registry.clear()
    
    def discard(self, ID):
        for registry in self.registries:
            if ID in registry: 
                registry.discard(ID)
                break
    
    def update(self, flowsheet):
        for registry, other_registry in zip(self.registries, flowsheet.registries):
            registry.data.update(other_registry.data)
    
    def to_dict(self):
        return {**self.stream.data,
                **self.unit.data,
                **self.system.data}
    
    @classmethod
    def from_flowsheets(cls, ID, flowsheets):
        """Return a new flowsheet with all registered objects from the given flowsheets."""
        new = cls(ID)
        isa = isinstance
        for flowsheet in flowsheets:
            if isa(flowsheet, str):
                flowsheet = cls.flowsheet[flowsheet]
            new.update(flowsheet)
        return new
    
    def diagram(self, kind=None, file=None, format=None, display=True, **graph_attrs):
        """
        Display all units and attached streams.
        
        Parameters
        ----------
        kind='surface' : 'cluster', 'thorough', 'surface', or 'minimal'
            * **'cluster':** Display all units clustered by system.
            * **'thorough':** Display every unit within the path.
            * **'surface':** Display only elements listed in the path.
            * **'minimal':** Display path as a box.
        file : str, display in console by default
            File name to save diagram.
        format : str
            File format (e.g. "png", "svg"). Defaults to 'png'.
        display : bool, optional
            Whether to display diagram in console or to return the graphviz 
            object.
            
        """
        return self.create_system(None).diagram(kind or 'thorough', file, format, display)
    
    def create_system(self, ID="", feeds=None, ends=(), facility_recycle=None):
        """
        Create a System object from all units and streams defined in the flowsheet.
        
        Parameters
        ----------
        ID : str, optional
            Name of system.
        feeds : Iterable[:class:`~thermosteam.Stream`], optional
            All feeds to the system. Specify this argument if only a section 
            of the complete system is wanted as it may disregard some units.
        ends : Iterable[:class:`~thermosteam.Stream`], optional
            End streams of the system which are not products. Specify this
            argument if only a section of the complete system is wanted, or if 
            recycle streams should be ignored.
        facility_recycle : :class:`~thermosteam.Stream`, optional
            Recycle stream between facilities and system path. This argument
            defaults to the outlet of a BlowdownMixer facility (if any).
        
        """
        return System.from_units(ID, self.unit, feeds, ends, facility_recycle)
    
    def create_network(self, feeds=None, ends=()):
        """
        Create a Network object from all units and streams defined in the flowsheet.
        
        Parameters
        ----------
        feeds : Iterable[:class:`~thermosteam.Stream`]
            Feeds to the process.
        ends : Iterable[:class:`~thermosteam.Stream`]
            End streams of the system which are not products. Specify this argument
			if only a section of the system is wanted, or if recycle streams should be 
			ignored.
        
        """
        feeds = feeds_from_units(self.unit)
        if feeds:
            sort_feeds_big_to_small(feeds)
            feedstock, *feeds = feeds
            network = Network.from_feedstock(feedstock, feeds, ends)
        else:
            network = Network([])
        return network
    
    def __call__(self, ID):
        """
		Return requested biosteam item.
    
        Parameters
        ----------
        ID : str
              ID of the requested item.
    
        """
        ID = ID.replace(' ', '_')
        obj = (self.stream.search(ID)
               or self.unit.search(ID)
               or self.system.search(ID))
        if not obj: raise LookupError(f"no registered item '{ID}'")
        return obj
    
    def __str__(self):
        return self.ID
    
    def __repr__(self):
        return f'<{type(self).__name__}: {self.ID}>'


class MainFlowsheet(Flowsheet):
    """
	Create a MainFlowsheet object which automatically registers 
    biosteam objects as they are created. For a tutorial on flowsheets,
    visit :doc:`tutorial/Managing_flowsheets`.
	"""
    
    __slots__ = ()
    
    line = "Main flowsheet"
        
    def set_flowsheet(self, flowsheet, new=False):
        """Set main flowsheet that is updated with new biosteam objects."""
        if isinstance(flowsheet, Flowsheet):
            dct = flowsheet.__dict__
        elif isinstance(flowsheet, str):
            if not new and flowsheet in self.flowsheet:
                dct = main_flowsheet.flowsheet[flowsheet].__dict__
            else:
                new_flowsheet = Flowsheet(flowsheet)
                self.flowsheet.__dict__[flowsheet] = new_flowsheet
                dct = new_flowsheet.__dict__
        else:
            raise TypeError('flowsheet must be a Flowsheet object')
        Stream.registry = dct['stream']
        System.registry = dct['system']
        Unit.registry = dct['unit']
        object.__setattr__(self, '__dict__', dct)
        
    def get_flowsheet(self):
        return self.flowsheet[self.ID]
        
    __setattr__ = Flowsheets.__setattr__
    
    def __new__(cls, ID):
        main_flowsheet.set_flowsheet(ID)
        return main_flowsheet

    def __repr__(self):
        return f'<{type(self).__name__}: {self.ID}>'
    
    
#: [main_flowsheet] Main flowsheet where objects are registered by ID.
main_flowsheet = object.__new__(MainFlowsheet)
main_flowsheet.set_flowsheet('default')
