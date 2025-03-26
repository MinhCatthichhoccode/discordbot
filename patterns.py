class PatternAnalyzer:
    """
    Class to analyze game patterns (cầu) in Tài Xỉu game.
    
    Patterns include:
    - Cầu bệt (Flat pattern): Same result appears multiple times in a row
    - Cầu đảo 1-1 (1-1 alternating pattern): Results alternate between Tài and Xỉu
    - Cầu 3-2-1 (3-2-1 pattern): Pattern with 3 of one result, then 2, then 1
    - Cầu đảo 1-2-3 (1-2-3 alternating pattern): Pattern with 1 of one result, then 2, then 3
    - Cầu nhịp nghiêng (Tilted rhythm pattern): Complex pattern with irregular alternation
    """
    
    def __init__(self, history=None):
        self.history = history or []
    
    def set_history(self, history):
        """Set the game history to analyze."""
        self.history = history
    
    def append_result(self, result):
        """Append a new result to the history."""
        self.history.append(result)
    
    def get_last_results(self, count=10):
        """Get the last N results."""
        return self.history[-count:] if len(self.history) >= count else self.history
    
    def detect_cau_bet(self, min_streak=3):
        """
        Detect Cầu bệt (Flat pattern) - same result appears multiple times in a row.
        Returns the current streak and the dominant result.
        """
        if not self.history:
            return 0, None
        
        current_streak = 1
        current_result = self.history[-1]
        
        # Count backward to find the streak
        for i in range(len(self.history) - 2, -1, -1):
            if self.history[i] == current_result:
                current_streak += 1
            else:
                break
        
        if current_streak >= min_streak:
            return current_streak, current_result
        else:
            return 0, None
    
    def detect_cau_dao_1_1(self, min_length=4):
        """
        Detect Cầu đảo 1-1 (1-1 alternating pattern) - results alternate between Tài and Xỉu.
        Returns the length of the alternating pattern.
        """
        if len(self.history) < min_length:
            return 0
        
        alternating_count = 1
        
        # Count backward to find alternating pattern
        for i in range(len(self.history) - 2, -1, -1):
            if self.history[i] != self.history[i+1]:
                alternating_count += 1
            else:
                break
        
        if alternating_count >= min_length:
            return alternating_count
        else:
            return 0
    
    def detect_cau_3_2_1(self):
        """
        Detect Cầu 3-2-1 (3-2-1 pattern) - Pattern with 3 of one result, then 2 of another, then 1.
        Returns True if the pattern is detected, False otherwise.
        """
        if len(self.history) < 6:
            return False
        
        # Get the last 6 results
        last_six = self.history[-6:]
        
        # Check if first 3 are the same
        if not (last_six[0] == last_six[1] == last_six[2]):
            return False
        
        # Check if next 2 are the same but different from the first 3
        if not (last_six[3] == last_six[4] and last_six[3] != last_six[0]):
            return False
        
        # Check if the last one is different from the previous 2
        if last_six[5] == last_six[3]:
            return False
        
        return True
    
    def detect_cau_dao_1_2_3(self):
        """
        Detect Cầu đảo 1-2-3 (1-2-3 alternating pattern) - Pattern with 1 of one result, then 2, then 3.
        Returns True if the pattern is detected, False otherwise.
        """
        if len(self.history) < 6:
            return False
        
        # Get the last 6 results
        last_six = self.history[-6:]
        
        # Define the expected pattern: 1 of A, 2 of B, 3 of A
        result_a = last_six[0]
        result_b = None
        
        # Check the second result is different
        if last_six[1] == result_a:
            return False
        result_b = last_six[1]
        
        # Check the pattern
        expected_pattern = [result_a, result_b, result_b, result_a, result_a, result_a]
        
        return last_six == expected_pattern
    
    def detect_cau_nhip_nghieng(self):
        """
        Detect Cầu nhịp nghiêng (Tilted rhythm pattern) - Complex pattern with irregular alternation.
        This is more complex and can be defined in various ways.
        One definition could be: A, A, B, A, B, B, A, A, B, B, B, A
        
        Returns True if the pattern is detected, False otherwise.
        """
        if len(self.history) < 12:
            return False
        
        # Get the last 12 results
        last_twelve = self.history[-12:]
        
        # Define result A as the first result
        result_a = last_twelve[0]
        
        # Find the first occurrence of a different result
        result_b = None
        for result in last_twelve:
            if result != result_a:
                result_b = result
                break
        
        if result_b is None:  # All results are the same
            return False
        
        # Define the expected tilted rhythm pattern
        expected_pattern = [
            result_a, result_a, result_b, 
            result_a, result_b, result_b, 
            result_a, result_a, result_b, 
            result_b, result_b, result_a
        ]
        
        return last_twelve == expected_pattern
    
    def analyze_patterns(self):
        """Analyze all patterns and return a summary."""
        results = {
            "cau_bet": self.detect_cau_bet(),
            "cau_dao_1_1": self.detect_cau_dao_1_1(),
            "cau_3_2_1": self.detect_cau_3_2_1(),
            "cau_dao_1_2_3": self.detect_cau_dao_1_2_3(),
            "cau_nhip_nghieng": self.detect_cau_nhip_nghieng()
        }
        
        return results
    
    def suggest_next_bet(self):
        """
        Suggest the next bet based on pattern analysis.
        This is intentionally made to be random so players must discover patterns.
        """
        if not self.history:
            return None
        
        # Randomize the suggestion to make players discover patterns
        if random.random() < 0.5:
            return "Tài" if self.history[-1] == "Xỉu" else "Xỉu"
        else:
            return self.history[-1]  # Suggest the same as last result
