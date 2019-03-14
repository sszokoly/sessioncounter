# sessioncounter #

This class keeps track of the concurrent active and peak SIP 
sessions by parsing SIP messages received through the update 
method. It is connection or host neutral, that is it doesn't 
care or know about the origin or destination of the message. 
Consumers should make sure SIP messages sent to an instance 
of this class belong to the same group of connections they 
desire to track. For example messages sent to or received 
from the same local interface, or same local or remote host 
address or service port.

