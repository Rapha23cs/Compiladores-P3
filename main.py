import sys


class Parser:
    def __init__(self, filename):
        """Inicializa o parser e carrega os comandos do arquivo .vm."""
        with open(filename, "r") as file:
            self.commands = [
                line.split("//")[0].strip().split()  # Remove comentários e divide tokens
                for line in file.readlines()
                if line.strip() and not line.startswith("//")
            ]
        self.current_command = None
        self.filename = filename.split("/")[-1].split(".")[0]

    def hasMoreCommands(self):
        """Retorna True se ainda há comandos a processar."""
        return bool(self.commands)

    def advance(self):
        """Lê o próximo comando e o define como corrente."""
        if self.hasMoreCommands():
            self.current_command = self.commands.pop(0)

    def commandType(self):
        """Retorna o tipo do comando."""
        if not self.current_command:  # Verifica se current_command está vazio
            return None  # Evita erro de índice

        if self.current_command[0] in {"add", "sub", "neg", "eq", "gt", "lt", "and", "or", "not"}:
            return "C_ARITHMETIC"
        elif self.current_command[0] == "push":
            return "C_PUSH"
        elif self.current_command[0] == "pop":
            return "C_POP"
        elif self.current_command[0] == "label":
            return "C_LABEL"
        elif self.current_command[0] == "goto":
            return "C_GOTO"
        elif self.current_command[0] == "if-goto":
            return "C_IF"
        elif self.current_command[0] == "function":
            return "C_FUNCTION"
        elif self.current_command[0] == "call":
            return "C_CALL"
        elif self.current_command[0] == "return":
            return "C_RETURN"
        else:
            raise ValueError(f"Comando desconhecido: {self.current_command[0]}")

    def arg1(self):
        """Retorna o primeiro argumento do comando."""
        if self.commandType() == "C_ARITHMETIC":
            return self.current_command[0]
        return self.current_command[1]

    def arg2(self):
        """Retorna o segundo argumento (apenas para Push, Pop, Function, Call)."""
        if self.commandType() in {"C_PUSH", "C_POP", "C_FUNCTION", "C_CALL"}:
            return int(self.current_command[2])
        raise ValueError(f"arg2 chamado para comando inválido: {self.current_command}")


class CodeWriter:
    SEGMENTS = {
        "local": "LCL",
        "argument": "ARG",
        "this": "THIS",
        "that": "THAT",
        "temp": "5",
        "pointer": "3",
        "static": "16"
    }

    def __init__(self, filename):
        """Abre o arquivo de saída e inicializa o CodeWriter."""
        self.file = open(filename, "w")
        self.label_count = 0
        self.filename = filename.split("/")[-1].split(".")[0]
        self.writeInit()  # Chama a inicialização automaticamente

    def writeInit(self):
        """Escreve o código de inicialização da VM."""
        asm_code = (
            "// Bootstrap code\n"
            "@256\nD=A\n@SP\nM=D\n"  # Inicializa SP=256
        )
        self.file.write(asm_code)

        # Configura ARG corretamente antes de chamar Sys.init
        self.writeCall("Sys.init", 0)

    def writeArithmetic(self, command):
        """Escreve código assembly para comandos aritméticos."""
        if command in {"add", "sub", "and", "or"}:
            op = {"add": "+", "sub": "-", "and": "&", "or": "|"}[command]
            asm_code = "@SP\nAM=M-1\nD=M\nA=A-1\nM=M" + op + "D\n"
        elif command in {"neg", "not"}:
            op = {"neg": "-", "not": "!"}[command]
            asm_code = "@SP\nA=M-1\nM=" + op + "M\n"
        elif command in {"eq", "gt", "lt"}:
            jump = {"eq": "JEQ", "gt": "JGT", "lt": "JLT"}[command]
            label_true = f"TRUE_{self.label_count}"
            label_end = f"END_{self.label_count}"
            asm_code = (
                "@SP\nAM=M-1\nD=M\nA=A-1\nD=M-D\n"
                f"@{label_true}\nD;{jump}\n"
                "@SP\nA=M-1\nM=0\n"
                f"@{label_end}\n0;JMP\n"
                f"({label_true})\n@SP\nA=M-1\nM=-1\n"
                f"({label_end})\n"
            )
            self.label_count += 1
        else:
            raise ValueError(f"Comando aritmético inválido: {command}")  # Adiciona erro explícito

        self.file.write(asm_code)

    def writePush(self, segment, index):
        """Escreve código assembly para comandos push."""
        if segment == "constant":
            asm_code = f"@{index}\nD=A\n"
        elif segment in self.SEGMENTS:
            base = self.SEGMENTS[segment]
            if segment in {"temp", "pointer", "static"}:
                asm_code = f"@{int(base) + index}\nD=M\n"
            else:
                asm_code = f"@{base}\nD=M\n@{index}\nA=D+A\nD=M\n"
        asm_code += "@SP\nA=M\nM=D\n@SP\nM=M+1\n"
        self.file.write(asm_code)

    def writePop(self, segment, index):
        """Escreve código assembly para comandos pop."""
        if segment in self.SEGMENTS:
            base = self.SEGMENTS[segment]
            if segment in {"temp", "pointer", "static"}:
                asm_code = f"@SP\nAM=M-1\nD=M\n@{int(base) + index}\nM=D\n"
            else:
                asm_code = f"@{base}\nD=M\n@{index}\nD=D+A\n@R13\nM=D\n@SP\nAM=M-1\nD=M\n@R13\nA=M\nM=D\n"
        self.file.write(asm_code)

    def writeCall(self, function_name, num_args):
        """Escreve código para chamar uma função."""
        return_label = f"RETURN_{self.label_count}"
        self.label_count += 1

        asm_code = (
            f"// call {function_name} {num_args}\n"
            f"@{return_label}\nD=A\n@SP\nA=M\nM=D\n@SP\nM=M+1\n"  # push return address
            "@LCL\nD=M\n@SP\nA=M\nM=D\n@SP\nM=M+1\n"  # push LCL
            "@ARG\nD=M\n@SP\nA=M\nM=D\n@SP\nM=M+1\n"  # push ARG
            "@THIS\nD=M\n@SP\nA=M\nM=D\n@SP\nM=M+1\n"  # push THIS
            "@THAT\nD=M\n@SP\nA=M\nM=D\n@SP\nM=M+1\n"  # push THAT
            f"@{num_args}\nD=A\n@5\nD=D+A\n@SP\nD=M-D\n@ARG\nM=D\n"  # ARG = SP - (num_args + 5)
            "@SP\nD=M\n@LCL\nM=D\n"  # LCL = SP
            f"@{function_name}\n0;JMP\n"  # Goto function
            f"({return_label})\n"  # (return label)
        )
        self.file.write(asm_code)

    def close(self):
        """Fecha o arquivo de saída."""
        self.file.close()


class VMTranslator:
    def __init__(self, input_file):
        """Inicializa o tradutor VM."""
        self.parser = Parser(input_file)
        output_file = input_file.replace(".vm", ".asm")
        self.code_writer = CodeWriter(output_file)

    def translate(self):
        """Traduz o arquivo VM para código Assembly."""
        while self.parser.hasMoreCommands():
            self.parser.advance()
            command_type = self.parser.commandType()

            if command_type == "C_ARITHMETIC":
                self.code_writer.writeArithmetic(self.parser.arg1())
            elif command_type == "C_PUSH":
                self.code_writer.writePush(self.parser.arg1(), self.parser.arg2())
            elif command_type == "C_POP":
                self.code_writer.writePop(self.parser.arg1(), self.parser.arg2())

        self.code_writer.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python VMTranslator.py arquivo.vm")
        sys.exit(1)
    translator = VMTranslator(sys.argv[1])
    translator.translate()
    print("Tradução concluída! Arquivo .asm gerado.")
