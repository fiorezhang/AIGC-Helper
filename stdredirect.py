import sys

class myStdout():
    def __init__(self):
        self.stdoutbak = sys.stdout
        self.stderrbak = sys.stderr
        sys.stdout = self
        sys.stderr = self
        
    def write(self,info):
       #info信息即标准输出sys.stdout和sys.stderr接收到的输出信息
       str = info.rstrip("\r\n")
       #if len(str):self.processInfo(str)  #对输出信息进行处理的方法
    
    def processInfo(self,info):
        self.stdoutbak.write("标准输出接收到消息："+info+"\n") #可以将信息再输出到原有标准输出，在定位问题时比较有用
	
    def restoreStd(self):
        #print("准备恢复标准输出")
        sys.stdout = self.stdoutbak 
        sys.stderr = self.stderrbak 
        #print("恢复标准输出完成")
        
    def flush(self):
        #print("清理缓冲区")
        pass

    def __del__(self):
       self.restoreStd()

#print("主程序开始运行,创建标准输出替代对象....")