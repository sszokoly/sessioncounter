"""
Copyright 2018 Szabolcs Szokoly <szokoly@protonmail.com>
This file is part of szokoly.
szokoly is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
szokoly is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
You should have received a copy of the GNU General Public License
along with szokoly.  If not, see <http://www.gnu.org/licenses/>.
"""

class SIPSessionCounter(object):
    """
    This class keeps track of the concurrent active and peak SIP 
    sessions by parsing SIP messages received through the update 
    method. It is connection or host neutral, that is it doesn't
    care or know about the origin or destination of the message. 
    Consumers should make sure SIP messages sent to an instance
    of this class belong to the same group of connections they
    desire to track. For example messages sent to or received 
    from the same local interface, or same local or remote host 
    address or service port.
    """
    
    def __init__(self, name=None, counters=None, peak_counters=None):
        self.name = name or "SessionCounter"
        self.counters = counters or defaultdict(int)
        self.peak_counters = peak_counters or defaultdict(int)
        self._callids = {}
        self._established = set()
    
    def update(self, sipmsg, direction=None):
        """
        Receives a SIP message and returns 1 if a change has
        occurred in the counters otherwise 0.
        """
        
        rv = 0
        direction = direction or "IN&OUT"
        callid = self.get_callid(sipmsg)
        
        if not self.is_response(sipmsg):
            return rv
        
        statuscode = self.get_statuscode(sipmsg)
        cseq, method = self.get_cseq(sipmsg)
        
        if method == "INVITE":
            if statuscode == "100" and not self.is_indialog(sipmsg):
                if callid not in self._callids:
                    direction = self.reverse_direction(direction)
                    self._callids[callid] = {"direction": direction,
                                             "cseqs": set([cseq])}
                    self.counters[direction] +=1
                    rv = 1
                else:
                    direction = self._callids[callid]["direction"]
                    self._callids[callid]["cseqs"].add(cseq)
            elif (statuscode == "200" and callid in self._callids and
                  callid not in self._established):
                self._established.add(callid)
            elif (statuscode.startswith(("3", "4", "5", "6")) and
                  callid in self._callids and
                  callid not in self._established):
                self._callids[callid]["cseqs"].discard(cseq)
                if not self._callids[callid]["cseqs"]:
                    direction = self._callids[callid]["direction"]
                    self._callids.pop(callid, None)
                    self.counters[direction] -=1
                    rv = 1
        
        elif method == "BYE":
            if callid in self._established:
                direction = self._callids[callid]["direction"]
                self._established.discard(callid)
                self._callids.pop(callid, None)
                self.counters[direction] -=1
                rv = 1
        
        current = self.sessions_sum
        if self.sessions_sum > self.peak_sessions_sum:
            self.peak_counters = copy(self.counters)
        
        return rv
    
    def reset_peak(self):
        self.peak = self.sessions_sum
        self.peak_counters = copy(self.counters)
    
    def clear(self):
        self.counters.clear()
        self.reset_peak()
    
    def __add__(self, other):
        if type(self) != type(other):
            raise TypeError("can only add SIPSessionCounter to another")
        new_name = "&".join((self.name, other.name))
        new_counters = defaultdict(int)
        new_peak_counters = defaultdict(int)
        for d in self.counters, other.counters:
            for k,v in d.items():
                new_counters[k] += v
        for d in self.peak_counters, other.peak_counters:
            for k,v in d.items():
                new_peak_counters[k] += v
        return SIPSessionCounter(name=new_name, counters=new_counters,
                                 peak_counters=new_peak_counters)
    
    def __str__(self):
        return "{0} {1}  Current: {2}  Peak: {3}".format(
            self.__class__.__name__,
            self.name,
            self.sessions_sum,
            self.peak_sessions_sum)
    
    @property
    def sessions(self):
        return dict(self.counters)
    
    @property
    def peak_sessions(self):
        return dict(self.peak_counters)
    
    @property
    def sessions_sum(self):
        return sum(self.counters.values())
    
    @property
    def peak_sessions_sum(self):
        return sum(self.peak_counters.values())
    
    @staticmethod
    def reverse_direction(direction):
        if direction == "IN&OUT":
            return direction
        return "IN" if direction == "OUT" else "IN"
    
    @staticmethod
    def get_callid(sipmsg):
        start = sipmsg.find("Call-ID:")
        if start == -1:
            start = sipmsg.find("i:")
            if start == -1:
                return ""
            start += 3
        else:
            start += 9
        end = sipmsg.find("\n", start)
        if end == -1:
            end = None
        return sipmsg[start:end].rstrip()
    
    @staticmethod
    def get_cseq(sipmsg):
        start = sipmsg.find("CSeq:")
        if start == -1:
            return -1, ""
        start += 6
        end = sipmsg.find("\n", start)
        if end == -1:
            end = None
        l = sipmsg[start:end].split()
        if len(l) == 2:
            return int(l[0]), l[1].rstrip()
        elif len(l) == 1:
            return 0, l[0].rstrip()
        return -1, ""
    
    @staticmethod
    def get_method(sipmsg):
        end = sipmsg.find(" ")
        if space > -1:
            return sipmsg[:end]
        return ""
    
    @staticmethod
    def get_statuscode(sipmsg):
        start = sipmsg.find(" ")
        if start > -1:
            start += 1
            end = sipmsg.find(" ", start)
            return sipmsg[start:end]
        return ""
    
    @staticmethod
    def is_indialog(sipmsg):
        start = sipmsg.find("To:")
        if start == -1:
            start = sipmsg.find("t:")
            if start == -1:
                return None
        end = sipmsg.find("\n", start)
        if end == -1:
            end = None
        header = sipmsg[start:end]
        start = header.find("tag")
        if start == -1:
            return False
        return True
    
    @staticmethod
    def is_response(sipmsg):
        return sipmsg.startswith("SIP/2.0")
    
    @staticmethod
    def is_request(sipmsg):
        return not self.is_response(sipmsg)

