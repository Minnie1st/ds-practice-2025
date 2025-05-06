### What about failure of the coordinator? Analyse the system and try to understand what are the consequences of a failing coordinator, during the execution of the commitment protocol. Think of a solution for this issue. No implementation is needed, but the points will only be awarded upon good analysis, justification, and solution.


If the coordinator (Order Executor) fails, it can cause problems in the 2PC protocol.


-Consequences:  
During Prepare: If the Order Executor fails after sending Prepare and gets a "yes" from participants, they wait for the next step. This can block the system until the coordinator is back.


During Commit: If it fails after sending Commit to one participant (e.g., Books Database) but not the other (e.g., Payment Service), it may cause inconsistency. For example, Books Database updates stock, but Payment Service does not process the payment.


During Abort: If it fails after sending Abort to one participant, the other might stay in an uncertain state.


-Analysis: This is a big problem because the coordinator controls the decision. Without it, participants don’t know what to do. Our system uses logs (executor_log_{REPLICA_ID}.json), but if the coordinator doesn’t recover, the transaction might stay stuck.


-Solution: We can use a backup coordinator. If the main Order Executor fails, another replica (e.g., order_executor_2) can take over using leader election (our code has run_election and monitor_leader). The new coordinator reads the log, checks the last state (e.g., PREPARING or COMMITTING), and retries Commit or Abort. This works because we have multiple Order Executors (1 to 4) and logs save the progress.


-Justification: This solution is good because it uses our existing leader election system. It avoids blocking and ensures consistency with minimal changes.
